import json
import time

import httpx
import pytest

from raiox.config import get_settings
from raiox.http import HostRateLimiter, HttpClient, RawStore, _retry_after_seconds, check_contract


@pytest.fixture
def settings(tmp_path):
    s = get_settings(offline=False)
    paths = s.paths.model_copy(
        update={"raw": str(tmp_path / "raw"), "state": str(tmp_path / "state")}
    )
    return s.model_copy(update={"paths": paths})


def _client(settings, handler, source="t"):
    c = HttpClient(settings, source, snapshot="2026-01-01")
    transport = httpx.MockTransport(handler)
    c._clients["api.test|0"] = httpx.Client(transport=transport)
    return c


def test_request_writes_raw_envelope_and_uses_cache(settings):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    c = _client(settings, handler)
    env = c.get_json("https://api.test/x", key="k1", params={"a": 1})
    assert env["body"] == {"ok": True}
    assert env["meta"]["sha256"] and env["meta"]["status"] == 200
    env2 = c.get_json("https://api.test/x", key="k1", params={"a": 1})
    assert env2["body"] == {"ok": True}
    assert len(calls) == 1  # segunda chamada veio do cache
    assert c.stats == {"network": 1, "cache": 1, "failed": 0}


def test_pagination_stops_on_short_page_and_total(settings):
    pages = {1: list(range(10)), 2: list(range(10, 20)), 3: list(range(20, 25))}

    def handler(request):
        p = int(request.url.params["pagina"])
        return httpx.Response(200, json={"resultado": pages.get(p, []), "totalPaginas": 3})

    c = _client(settings, handler)
    envs = list(c.paginate("https://api.test/p", {}, "pg", page_size=10))
    assert [len(e["body"]["resultado"]) for e in envs] == [10, 10, 5]


def test_pagination_guard_against_repeated_page(settings):
    def handler(request):
        return httpx.Response(200, json={"resultado": list(range(10))})

    c = _client(settings, handler)
    envs = list(c.paginate("https://api.test/p", {}, "rep", page_size=10))
    assert len(envs) == 1


def test_resume_reuses_cached_pages(settings):
    calls = []

    def handler(request):
        p = int(request.url.params["pagina"])
        calls.append(p)
        return httpx.Response(
            200, json={"resultado": [p] * 10 if p < 3 else [p], "totalPaginas": 3}
        )

    c = _client(settings, handler)
    list(c.paginate("https://api.test/p", {}, "res", page_size=10))
    # "queda": apaga a última página e roda de novo
    c.store.path("res_p0003").unlink()
    calls.clear()
    list(c.paginate("https://api.test/p", {}, "res", page_size=10))
    assert calls == [3]


def test_definitive_failure_returns_none_and_is_counted(settings):
    def handler(request):
        return httpx.Response(404, json={"message": "Resource not found"})

    c = _client(settings, handler)
    assert c.get_json("https://api.test/missing", key="m") is None
    assert c.stats["failed"] == 1


def test_offline_mode_never_hits_network(tmp_path):
    s = get_settings(offline=True)
    paths = s.paths.model_copy(update={"fixtures": str(tmp_path)})
    s = s.model_copy(update={"paths": paths})
    store = RawStore(tmp_path / "raw", "src", "2026-01-01")
    store.write("k", {"meta": {}, "body": [1, 2]})
    c = HttpClient(s, "src")
    assert c.snapshot == "2026-01-01"
    assert c.get_json("https://never.called/", key="k")["body"] == [1, 2]
    assert c.get_json("https://never.called/", key="missing") is None


def test_contract_check_reports_new_and_missing():
    res = check_contract("ep.test", {"a": 1, "novo": 2}, {"a", "b"}, {"b"})
    assert res == {"new": ["novo"], "missing": ["b"]}
    assert check_contract("ep.test", {}, {"a"}) == {"new": [], "missing": []}  # só na 1ª vez


def test_retry_after_parsing_and_rate_limiter():
    r = httpx.Response(429, headers={"Retry-After": "3"})
    assert _retry_after_seconds(r) == 3.0
    assert _retry_after_seconds(httpx.Response(429)) is None
    lim = HostRateLimiter({"h": 20.0})
    t0 = time.monotonic()
    for _ in range(3):
        lim.wait("h")
    assert time.monotonic() - t0 >= 0.09


def test_raw_store_roundtrip(tmp_path):
    st = RawStore(tmp_path, "s", "snap")
    st.write("a/b c", {"meta": {"x": 1}, "body": {"y": 2}})
    assert st.exists("a/b c")
    keys = [k for k, _ in st.iter_envelopes()]
    assert keys == ["a_b_c"]
    assert json.loads(st.path("a/b c").read_text(encoding="utf-8"))["body"] == {"y": 2}
