"""Cliente HTTP robusto e compartilhado por todas as fontes.

Recursos (seção 7.1 do SUPERPROMPT):
- httpx (HTTP/1.1) com timeout configurável e User-Agent do projeto;
- retry com tenacity (timeouts, conexão, 429, 5xx), backoff exponencial com jitter,
  respeitando Retry-After;
- rate limit por host (token bucket simples, thread-safe);
- cache em disco no raw do snapshot do dia (não chama de novo o que já foi baixado);
- paginação genérica com trava contra loop infinito e retomada;
- TLS: certifi → truststore → cadeia ICP-Brasil em certs/. Nunca desabilita verificação.
- modo offline: só lê data/fixtures/raw, nunca acessa a rede.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
import httpx
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from raiox.config import Settings
from raiox.logs import logger

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class SourceUnavailable(RuntimeError):
    """Falha definitiva ao consultar uma fonte (após todos os retries)."""


# --------------------------------------------------------------------------- #
# Raw store                                                                   #
# --------------------------------------------------------------------------- #
def safe_key(text: str) -> str:
    """Nome de arquivo seguro (Windows) para uma chave de cache."""
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", text).strip("_")[:150]


@dataclass
class RawStore:
    """Raw imutável: data/raw/<fonte>/<snapshot>/<chave>.json."""

    root: Path
    source: str
    snapshot: str

    @property
    def dir(self) -> Path:
        return self.root / self.source / self.snapshot

    def path(self, key: str) -> Path:
        return self.dir / f"{safe_key(key)}.json"

    def exists(self, key: str) -> bool:
        return self.path(key).exists()

    def read(self, key: str) -> dict[str, Any]:
        with self.path(key).open(encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, key: str, envelope: dict[str, Any]) -> Path:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(envelope, fh, ensure_ascii=False)
        tmp.replace(path)
        return path

    def iter_envelopes(self, prefix: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
        if not self.dir.exists():
            return
        for p in sorted(self.dir.glob(f"{safe_key(prefix)}*.json")):
            with p.open(encoding="utf-8") as fh:
                yield p.stem, json.load(fh)


def list_snapshots(raw_root: Path, source: str) -> list[str]:
    base = raw_root / source
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


# --------------------------------------------------------------------------- #
# Rate limit                                                                  #
# --------------------------------------------------------------------------- #
class HostRateLimiter:
    """Token bucket simples (capacidade 1) por host, seguro entre threads."""

    def __init__(self, rates: dict[str, float]):
        self.rates = rates
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        rate = self.rates.get(host, self.rates.get("default", 1.0))
        interval = 1.0 / rate if rate > 0 else 0.0
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next.get(host, now))
            self._next[host] = start + interval
        delay = start - time.monotonic()
        if delay > 0:
            time.sleep(delay)


# --------------------------------------------------------------------------- #
# TLS                                                                         #
# --------------------------------------------------------------------------- #
TLS_MODES = ("certifi", "truststore", "icp-brasil")


def build_ssl_context(mode: str, certs_dir: Path) -> ssl.SSLContext:
    """Contexto TLS com verificação SEMPRE ligada (seção 7.4)."""
    if mode == "certifi":
        return ssl.create_default_context(cafile=certifi.where())
    if mode == "truststore":
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if mode == "icp-brasil":
        bundle = certs_dir / "icp-brasil.pem"
        if not bundle.exists():
            raise FileNotFoundError(
                f"Cadeia ICP-Brasil não encontrada em {bundle}. Baixe do ITI (ver docs/FONTES.md)."
            )
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cafile=str(bundle))
        return ctx
    raise ValueError(f"Modo TLS desconhecido: {mode}")


def ensure_icp_bundle(settings: Settings) -> Path | None:
    """Baixa a cadeia ICP-Brasil do ITI (zip oficial) e gera certs/icp-brasil.pem.

    O download em si é verificado com certifi/truststore. Retorna None se falhar.
    """
    import io
    import zipfile

    bundle = settings.root / settings.paths.certs / "icp-brasil.pem"
    if bundle.exists():
        return bundle
    url = settings.http.icp_brasil_bundle_url
    for mode in ("certifi", "truststore"):
        try:
            ctx = build_ssl_context(mode, bundle.parent)
            with httpx.Client(verify=ctx, timeout=60, follow_redirects=True) as c:
                resp = c.get(url, headers={"User-Agent": settings.user_agent})
                resp.raise_for_status()
            pems = []
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    data = zf.read(name)
                    if b"-----BEGIN CERTIFICATE-----" in data:
                        pems.append(data.decode("ascii", "ignore"))
                    elif name.lower().endswith((".crt", ".cer", ".der")):
                        pems.append(ssl.DER_cert_to_PEM_cert(data))
            bundle.parent.mkdir(parents=True, exist_ok=True)
            bundle.write_text("\n".join(pems), encoding="ascii")
            logger.info("Cadeia ICP-Brasil salva em {} ({} certificados)", bundle, len(pems))
            return bundle
        except Exception as exc:  # noqa: BLE001
            logger.warning("Não foi possível baixar a cadeia ICP-Brasil ({}): {!r}", mode, exc)
    return None


def _is_ssl_error(exc: BaseException) -> bool:
    cur: BaseException | None = exc
    while cur is not None:
        if isinstance(cur, ssl.SSLError):
            return True
        if "CERTIFICATE_VERIFY_FAILED" in str(cur):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


# --------------------------------------------------------------------------- #
# Cliente                                                                     #
# --------------------------------------------------------------------------- #
_LIMITER: HostRateLimiter | None = None
_LIMITER_LOCK = threading.Lock()


def _limiter(settings: Settings) -> HostRateLimiter:
    global _LIMITER
    with _LIMITER_LOCK:
        if _LIMITER is None:
            _LIMITER = HostRateLimiter(settings.http.rate_limits)
        return _LIMITER


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    if _is_ssl_error(exc):
        return False
    return isinstance(exc, httpx.TransportError)


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            return max(0.0, (when - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError):
            return None


class _WaitWithRetryAfter:
    def __init__(self, initial: float, maximum: float):
        self._exp = wait_random_exponential(multiplier=initial, max=maximum)
        self._max = maximum

    def __call__(self, state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        if isinstance(exc, httpx.HTTPStatusError):
            ra = _retry_after_seconds(exc.response)
            if ra is not None:
                return min(ra, self._max * 2)
        return self._exp(state)


def today_snapshot() -> str:
    return date.today().isoformat()


class HttpClient:
    """Cliente de uma fonte. Grava cada resposta no raw e reaproveita o cache do snapshot."""

    def __init__(
        self,
        settings: Settings,
        source: str,
        snapshot: str | None = None,
        force: bool = False,
    ):
        self.settings = settings
        self.source = source
        self.offline = settings.offline
        self.force = force and not self.offline
        raw_root = settings.path("raw")
        if snapshot is None:
            snapshot = self._offline_snapshot(raw_root) if self.offline else today_snapshot()
        self.store = RawStore(raw_root, source, snapshot)
        self._clients: dict[str, httpx.Client] = {}
        self._tls_mode: dict[str, int] = {}
        self._lock = threading.Lock()
        self.stats = {"network": 0, "cache": 0, "failed": 0}

    # -- infraestrutura -------------------------------------------------------
    def _offline_snapshot(self, raw_root: Path) -> str:
        snaps = list_snapshots(raw_root, self.source)
        return snaps[-1] if snaps else "fixtures"

    @property
    def snapshot(self) -> str:
        return self.store.snapshot

    def _client_for(self, host: str) -> httpx.Client:
        with self._lock:
            mode_idx = self._tls_mode.get(host, 0)
            key = f"{host}|{mode_idx}"
            if key not in self._clients:
                ctx = build_ssl_context(TLS_MODES[mode_idx], self.settings.root / "certs")
                self._clients[key] = httpx.Client(
                    timeout=httpx.Timeout(self.settings.http.timeout_s, connect=30.0),
                    headers={"User-Agent": self.settings.user_agent, "Accept": "*/*"},
                    verify=ctx,
                    http2=False,
                    follow_redirects=True,
                )
            return self._clients[key]

    def _escalate_tls(self, host: str) -> bool:
        with self._lock:
            idx = self._tls_mode.get(host, 0)
            if idx + 1 >= len(TLS_MODES):
                return False
            nxt = idx + 1
            if TLS_MODES[nxt] == "icp-brasil" and ensure_icp_bundle(self.settings) is None:
                return False
            self._tls_mode[host] = nxt
        logger.warning("TLS: erro de certificado em {}; tentando modo '{}'", host, TLS_MODES[nxt])
        return True

    def close(self) -> None:
        for c in self._clients.values():
            c.close()
        self._clients.clear()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- requisição -----------------------------------------------------------
    def _send(self, method: str, url: str, params: dict | None, body: Any | None) -> httpx.Response:
        host = urlparse(url).hostname or "default"
        cfg = self.settings.http

        def attempt() -> httpx.Response:
            _limiter(self.settings).wait(host)
            client = self._client_for(host)
            resp = client.request(method, url, params=params, json=body)
            if resp.status_code in RETRYABLE_STATUS:
                logger.debug("{} {} → {} (vai tentar de novo)", method, url, resp.status_code)
                resp.raise_for_status()
            return resp

        retrying = Retrying(
            retry=retry_if_exception(_retryable),
            stop=stop_after_attempt(cfg.max_attempts),
            wait=_WaitWithRetryAfter(cfg.backoff_initial_s, cfg.backoff_max_s),
            reraise=True,
            before_sleep=lambda st: logger.info(
                "Retry {}/{} em {} ({})",
                st.attempt_number,
                cfg.max_attempts,
                host,
                type(st.outcome.exception()).__name__ if st.outcome else "?",
            ),
        )
        while True:
            try:
                return retrying(attempt)
            except Exception as exc:  # noqa: BLE001
                if _is_ssl_error(exc) and self._escalate_tls(host):
                    continue
                raise

    def request(
        self,
        method: str,
        url: str,
        key: str,
        params: dict | None = None,
        body: Any | None = None,
        expect: str = "json",
    ) -> dict[str, Any] | None:
        """Faz (ou lê do cache) uma chamada e devolve o envelope {meta, body}.

        Retorna None em falha definitiva (logada com URL, parâmetros e corpo truncado)
        ou, no modo offline, quando a fixture não existe.
        """
        if self.store.exists(key) and not self.force:
            self.stats["cache"] += 1
            return self.store.read(key)
        if self.offline:
            logger.debug("Offline: fixture ausente {}/{}", self.source, key)
            return None

        t0 = time.perf_counter()
        try:
            resp = self._send(method, url, params, body)
        except Exception as exc:  # noqa: BLE001
            self.stats["failed"] += 1
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError):
                detail = exc.response.text[:500]
            logger.error(
                "Falha definitiva [{}] {} {} params={} body={} erro={} resposta={!r}",
                self.source,
                method,
                url,
                params,
                json.dumps(body, ensure_ascii=False)[:300] if body else None,
                repr(exc)[:300],
                detail,
            )
            return None
        elapsed = time.perf_counter() - t0
        raw_bytes = resp.content
        if resp.status_code >= 400:
            self.stats["failed"] += 1
            logger.error(
                "HTTP {} [{}] {} params={} resposta={!r}",
                resp.status_code,
                self.source,
                url,
                params,
                resp.text[:500],
            )
            return None
        if expect == "json":
            try:
                payload: Any = resp.json()
            except ValueError:
                self.stats["failed"] += 1
                logger.error(
                    "Resposta não-JSON de {} params={}: {!r}", url, params, resp.text[:300]
                )
                return None
        else:
            payload = resp.text
        envelope = {
            "meta": {
                "source": self.source,
                "url": str(resp.request.url),
                "method": method,
                "params": params,
                "body": body,
                "status": resp.status_code,
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "elapsed_s": round(elapsed, 3),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "bytes": len(raw_bytes),
            },
            "body": payload,
        }
        self.store.write(key, envelope)
        self.stats["network"] += 1
        return envelope

    def get_json(self, url: str, key: str, params: dict | None = None) -> dict[str, Any] | None:
        return self.request("GET", url, key, params=params)

    def post_json(self, url: str, key: str, body: Any) -> dict[str, Any] | None:
        return self.request("POST", url, key, body=body)

    def download(self, url: str, dest: Path) -> Path | None:
        """Download em streaming de um arquivo grande (CSV/ZIP). Não usa o cache JSON."""
        if self.offline:
            return dest if dest.exists() else None
        if dest.exists() and not self.force:
            return dest
        host = urlparse(url).hostname or "default"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        for _ in range(len(TLS_MODES)):
            try:
                _limiter(self.settings).wait(host)
                with self._client_for(host).stream("GET", url) as resp:
                    resp.raise_for_status()
                    with tmp.open("wb") as fh:
                        for chunk in resp.iter_bytes(1 << 20):
                            fh.write(chunk)
                tmp.replace(dest)
                return dest
            except Exception as exc:  # noqa: BLE001
                if _is_ssl_error(exc) and self._escalate_tls(host):
                    continue
                logger.error("Falha no download {}: {!r}", url, exc)
                return None
        return None

    # -- paginação ------------------------------------------------------------
    def paginate(
        self,
        url: str,
        params: dict[str, Any],
        key_prefix: str,
        page_size: int,
        page_param: str = "pagina",
        size_param: str = "tamanhoPagina",
        results_field: str = "resultado",
        total_pages_field: str = "totalPaginas",
    ) -> Iterator[dict[str, Any]]:
        """Itera páginas até: página vazia, página menor que o tamanho, total atingido,
        página repetida (trava anti-loop) ou max_pages. Páginas já baixadas no snapshot
        vêm do cache, então interromper e rodar de novo retoma de onde parou."""
        seen_hashes: set[str] = set()
        page = 1
        max_pages = self.settings.http.max_pages
        while page <= max_pages:
            q = dict(params)
            q[page_param] = page
            q[size_param] = page_size
            env = self.get_json(url, key=f"{key_prefix}_p{page:04d}", params=q)
            if env is None:
                if not self.offline:
                    logger.warning("Paginação interrompida em {} página {}", key_prefix, page)
                return
            body = env["body"]
            rows = body.get(results_field, []) if isinstance(body, dict) else body
            if not rows:
                return
            digest = hashlib.sha256(
                json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            if digest in seen_hashes:
                logger.warning("Página repetida em {} (página {}): parando.", key_prefix, page)
                return
            seen_hashes.add(digest)
            yield env
            total_pages = body.get(total_pages_field) if isinstance(body, dict) else None
            if len(rows) < page_size:
                return
            if total_pages is not None and page >= int(total_pages):
                return
            page += 1
        logger.warning("Limite de {} páginas atingido em {}", max_pages, key_prefix)


# --------------------------------------------------------------------------- #
# Validação de contrato (seção 7.2)                                           #
# --------------------------------------------------------------------------- #
_CONTRACT_SEEN: set[str] = set()


def check_contract(
    endpoint: str,
    record: dict[str, Any],
    expected: set[str],
    critical: set[str] | None = None,
) -> dict[str, list[str]]:
    """Compara as chaves do primeiro registro com as esperadas (uma vez por endpoint)."""
    if endpoint in _CONTRACT_SEEN:
        return {"new": [], "missing": []}
    _CONTRACT_SEEN.add(endpoint)
    keys = set(record)
    new = sorted(keys - expected)
    missing = sorted(expected - keys)
    if new:
        logger.info("Contrato {}: campos novos (ok) {}", endpoint, new)
    if missing:
        crit = sorted(set(missing) & (critical or set()))
        log = logger.error if crit else logger.warning
        log("Contrato {}: campos esperados ausentes {} (críticos: {})", endpoint, missing, crit)
    return {"new": new, "missing": missing}
