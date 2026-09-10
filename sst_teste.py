"""Entrada estável e profissional do ambiente de desenvolvimento SST/EPI."""

from __future__ import annotations

import streamlit as st

from sst_ui import aplicar_estilo_sst, renderizar_aviso_desenvolvimento, renderizar_logo


st.set_page_config(
    page_title="Copa Gestão | SST/EPI",
    page_icon="⛑️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

aplicar_estilo_sst()
renderizar_aviso_desenvolvimento()

if "sst_modulo_aberto" not in st.session_state:
    st.session_state["sst_modulo_aberto"] = False

if not st.session_state["sst_modulo_aberto"]:
    topo_esq, topo_dir = st.columns([4, 1], vertical_alignment="center")
    with topo_esq:
        renderizar_logo(190)
    with topo_dir:
        st.caption("COPA GESTÃO")
        st.markdown("**Portal interno SST**")

    st.divider()

    espaco1, centro, espaco2 = st.columns([1.15, 2.7, 1.15])
    with centro:
        st.markdown("<div class='sst-kicker'>Segurança, controle e rastreabilidade</div>", unsafe_allow_html=True)
        st.markdown("<div class='sst-hero-title'>⛑️ SST / EPI</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='sst-hero-text'>Um ambiente único para organizar colaboradores, EPIs, "
            "entregas, documentos de SST e o fluxo de assinatura biométrica.</div>",
            unsafe_allow_html=True,
        )
        st.write("")

        c1, c2, c3 = st.columns(3)
        c1.metric("Módulo", "SST / EPI")
        c2.metric("Ambiente", "Desenvolvimento")
        c3.metric("Rastreabilidade", "Ativa")

        st.write("")
        if st.button("Entrar no módulo SST/EPI", type="primary", use_container_width=True):
            st.session_state["sst_modulo_aberto"] = True
            st.rerun()

        st.caption(
            "Colaboradores • Controle de CA • Entregas • Documentos / OS de SST • Assinaturas"
        )
else:
    try:
        from sst_app import renderizar_modulo_sst

        actor_teste = {
            "usuario": "admin",
            "nome": "Ambiente de Desenvolvimento",
            "nivel": 4.0,
        }

        if st.button("← Voltar ao portal SST", use_container_width=False):
            st.session_state["sst_modulo_aberto"] = False
            st.rerun()

        renderizar_modulo_sst(actor_teste)

    except Exception as exc:
        st.error("Não foi possível carregar o módulo SST/EPI.")
        st.exception(exc)
        if st.button("Voltar ao portal SST", type="primary"):
            st.session_state["sst_modulo_aberto"] = False
            st.rerun()
