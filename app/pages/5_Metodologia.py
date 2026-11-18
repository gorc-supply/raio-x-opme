"""Metodologia: renderiza docs/METODOLOGIA.md."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Metodologia")
c.filters()
text = c.doc("METODOLOGIA.md")
c.page_title("Metodologia", "menu_book")
body = text.split("\n", 1)[1] if text.startswith("# ") else text
st.markdown(body or "Documento não encontrado (docs/METODOLOGIA.md).")
c.footer()
