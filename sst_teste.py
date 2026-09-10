"""
Entrada do ambiente de desenvolvimento do módulo SST/EPI.
Não substitui o app.py de produção.
"""

import streamlit as st

st.set_page_config(
    page_title="Copa Gestão - SST/EPI (Desenvolvimento)",
    page_icon="🦺",
    layout="wide",
)

st.warning("🧪 AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI")
st.caption(
    "Esta interface é destinada aos testes do novo módulo e não substitui "
    "o sistema oficial de manutenção."
)

# Importamos o módulo somente depois de a página do Streamlit já estar montada.
# Isso evita uma tela totalmente branca caso o ambiente esteja reiniciando.
try:
    from sst_app import renderizar_modulo_sst

    actor_teste = {
        "usuario": "admin",
        "nome": "Ambiente de Desenvolvimento",
        "nivel": 4.0,
    }

    renderizar_modulo_sst(actor_teste)

except Exception as exc:
    st.error("Não foi possível carregar o módulo SST/EPI.")
    st.exception(exc)
