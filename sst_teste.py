"""
Aplicação de teste isolada do módulo SST/EPI.

Execute este arquivo apenas no ambiente/branch de desenvolvimento.
Ele não substitui o app.py do sistema de manutenção.
"""

import streamlit as st

from sst_app import renderizar_modulo_sst

st.set_page_config(
    page_title="Copa Gestão - SST/EPI (Teste)",
    page_icon="🦺",
    layout="wide",
)

st.warning("🧪 AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI")
st.caption(
    "Esta interface é destinada aos testes do novo módulo e não substitui "
    "o sistema oficial de manutenção."
)

# Ator temporário somente para a interface de desenvolvimento.
# Quando integrarmos ao sistema matriz, será substituído pelo usuário
# autenticado no login principal.
actor_teste = {
    "usuario": "desenvolvimento-sst",
    "nome": "Ambiente de Desenvolvimento",
    "nivel": 4.0,
}

renderizar_modulo_sst(actor_teste)
