"""Entrada estável do ambiente de desenvolvimento SST/EPI."""

import streamlit as st

st.set_page_config(
    page_title="Copa Gestão - SST/EPI (Desenvolvimento)",
    page_icon="🦺",
    layout="wide",
)

from sst_ui import aplicar_estilo_sst, renderizar_portal_inicial

aplicar_estilo_sst()

st.warning("🧪 AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI")
st.caption(
    "Esta interface é destinada aos testes do novo módulo e não substitui "
    "o sistema oficial de manutenção."
)

if "sst_modulo_aberto" not in st.session_state:
    st.session_state["sst_modulo_aberto"] = False

if not st.session_state["sst_modulo_aberto"]:
    renderizar_portal_inicial()
    if st.button("Entrar no módulo SST/EPI", type="primary", use_container_width=True):
        st.session_state["sst_modulo_aberto"] = True
        st.rerun()
else:
    try:
        from sst_app import renderizar_modulo_sst

        actor_teste = {
            "usuario": "admin",
            "nome": "Ambiente de Desenvolvimento",
            "nivel": 4.0,
        }

        if st.button("← Voltar para a tela inicial", use_container_width=False):
            st.session_state["sst_modulo_aberto"] = False
            st.rerun()

        renderizar_modulo_sst(actor_teste)
    except Exception as exc:
        st.error("Não foi possível carregar o módulo SST/EPI.")
        st.exception(exc)
        if st.button("Voltar para a tela inicial", type="primary"):
            st.session_state["sst_modulo_aberto"] = False
            st.rerun()
