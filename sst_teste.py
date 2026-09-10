"""Entrada estável e profissional do ambiente de desenvolvimento SST/EPI."""

from __future__ import annotations

import streamlit as st

from sst_ui import (
    aplicar_estilo_sst,
    renderizar_aviso_desenvolvimento,
    renderizar_portal_inicial,
    renderizar_topo_portal,
)


st.set_page_config(
    page_title="Copa Gestão | SST/EPI",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

aplicar_estilo_sst()
renderizar_aviso_desenvolvimento()

if "sst_modulo_aberto" not in st.session_state:
    st.session_state["sst_modulo_aberto"] = False

if not st.session_state["sst_modulo_aberto"]:
    renderizar_topo_portal()
    renderizar_portal_inicial()

    _, centro, _ = st.columns([1.15, 3.7, 1.15])
    with centro:
        if st.button(
            "Entrar no módulo SST/EPI",
            type="primary",
            use_container_width=True,
            icon=":material/login:",
        ):
            st.session_state["sst_modulo_aberto"] = True
            st.rerun()

        st.markdown(
            """
            <div class="sst-module-line">
                Colaboradores • Controle de CA • Entregas de EPI • Documentos / OS de SST • Assinaturas
            </div>
            """,
            unsafe_allow_html=True,
        )

else:
    try:
        from sst_app import renderizar_modulo_sst

        actor_teste = {
            "usuario": "admin",
            "nome": "Ambiente de Desenvolvimento",
            "nivel": 4.0,
        }

        col_voltar, _ = st.columns([1.4, 6])
        with col_voltar:
            if st.button("← Voltar ao portal SST", use_container_width=True):
                st.session_state["sst_modulo_aberto"] = False
                st.rerun()

        renderizar_modulo_sst(actor_teste)

    except Exception as exc:
        st.error("Não foi possível carregar o módulo SST/EPI.")
        st.exception(exc)

        if st.button("Voltar ao portal SST", type="primary"):
            st.session_state["sst_modulo_aberto"] = False
            st.rerun()
