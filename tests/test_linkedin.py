"""Regras da seção 9 aplicadas aos rascunhos de post e aos gráficos."""

import re
from pathlib import Path

import pytest

from raiox.schemas import FORBIDDEN_WORDS

ROOT = Path(__file__).resolve().parents[1]
POSTS = sorted((ROOT / "linkedin" / "posts").glob("0*.md"))


def test_there_are_five_posts():
    assert len(POSTS) == 5


@pytest.mark.parametrize("post", POSTS, ids=lambda p: p.stem)
def test_post_rules(post):
    text = post.read_text(encoding="utf-8").strip()
    assert len(text) <= 1300, f"{post.name}: {len(text)} caracteres"
    tags = re.findall(r"(?<!\w)#\w+", text)
    assert 3 <= len(tags) <= 5
    assert "streamlit.app" in text  # link do painel no fim
    low = text.lower()
    assert not any(w in low for w in FORBIDDEN_WORDS)
    assert "fonte" in low


def test_charts_are_4x5_when_present():
    from PIL import Image

    pngs = sorted((ROOT / "linkedin" / "graficos").glob("*.png"))
    for p in pngs:
        assert Image.open(p).size == (1080, 1350), p.name
