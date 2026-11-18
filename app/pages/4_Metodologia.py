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
st.markdown(text or "# Metodologia\n\nDocumento não encontrado (docs/METODOLOGIA.md).")
c.footer()
