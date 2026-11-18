"""Smoke test do painel com streamlit.testing.v1.AppTest (todas as páginas, sem rede)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = sorted(f"pages/{p.name}" for p in (APP / "pages").glob("*.py"))


def _no_errors(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def _home() -> AppTest:
    return AppTest.from_file(str(APP / "Home.py"), default_timeout=180).run()


def test_home_renders_kpis_and_findings():
    at = _home()
    _no_errors(at)
    hero = [m.value for m in at.markdown if 'class="rx-hero"' in m.value]
    assert hero and "Raio-X OPME" in hero[0]
    assert len(at.metric) >= 4
    # Achados fortes em cards, com selo de robustez.
    assert any('class="rx-badge forte"' in m.value for m in at.markdown)


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders(page):
    at = _home()
    at.switch_page(page).run()
    _no_errors(at)


@pytest.mark.parametrize("page", [p for p in PAGES if "/1_" in p or "/2_" in p])
def test_item_pages_work_for_every_item(page):
    at = _home()
    at.switch_page(page).run()
    for code in list(at.sidebar.selectbox(key="f_item").options):
        value = int(str(code).split("(")[-1].rstrip(")"))
        at.sidebar.selectbox(key="f_item").set_value(value).run()
        _no_errors(at)


def test_filters_persist_across_pages():
    at = _home()
    at.sidebar.toggle(key="f_outliers").set_value(True).run()
    _no_errors(at)
    at.switch_page("pages/3_Importacao.py").run()
    _no_errors(at)
    assert at.sidebar.toggle(key="f_outliers").value is True


def test_dashboard_never_calls_network(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise AssertionError("o painel não pode chamar a rede")

    monkeypatch.setattr(httpx.Client, "send", boom)
    at = _home()
    _no_errors(at)
    for page in PAGES:
        at.switch_page(page).run()
        _no_errors(at)
