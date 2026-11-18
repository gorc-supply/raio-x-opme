"""Sobre o projeto e o autor."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Sobre")
c.filters()
info = c.settings_info()
m = c.meta()
st.title("Sobre")
st.markdown(
    f"""
**Raio-X OPME** é um projeto open source que mostra quanto o setor público brasileiro paga por
órteses, próteses e materiais especiais (stents, próteses articulares, placas e parafusos,
marca-passos, endopróteses, cateteres), como esse preço varia entre estados e quanto o país
depende de importação nesses itens.

### Autor
**Gabriel Cunha** — profissional de Supply Chain & Operations com vivência em OPME.

- LinkedIn: [{c.LINKEDIN.removeprefix("https://www.")}]({c.LINKEDIN})
- Repositório: [{info["repo_url"].removeprefix("https://")}]({info["repo_url"]})

### Licença
Código sob licença **MIT**. Os dados são públicos e pertencem às fontes originais
(Compras.gov.br, ComexStat/MDIC, Banco Central, IBGE e ANVISA); cite-as ao reutilizar.

### Como citar
> Cunha, Gabriel. *Raio-X OPME: preços públicos de órteses, próteses e materiais especiais no Brasil*.
> Dados até {m.get("snapshot_dados", "—")}. Disponível em: {info["repo_url"]}.

### Aviso
Diferença de preço não é sinônimo de irregularidade. Volume, prazo, logística, consignação,
especificação técnica e urgência explicam boa parte da variação. Os números aqui são indícios
para investigação e debate, sempre com período, tamanho de amostra e fonte.
"""
)
c.footer()
