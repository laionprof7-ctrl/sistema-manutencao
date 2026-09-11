from __future__ import annotations

import streamlit as st

import sst_app_core as core


AREAS = [
    ("Visão Geral", "Visão Geral", core._render_dashboard),
    ("Colaboradores", "Colaboradores", core._render_colaboradores),
    ("Controle de GHE", "Controle de GHE", core._render_ghes),
    ("Gestão de Registros de EPI", "Gestão de Registros de EPI", core._render_epis),
    ("Entrega de EPI", "Entrega de EPI", core._render_entregas),
    ("Documentações SST", "Documentações SST", core._render_documentos),
    ("Assinaturas de Documentos", "Assinaturas de Documentos", core._render_assinaturas),
]


def _abrir_area(nome: str) -> None:
    st.session_state["sst_area_ativa"] = nome


def _voltar_menu() -> None:
    st.session_state.pop("sst_area_ativa", None)
    st.session_state.pop("sst_assinatura_documento", None)


def _render_menu() -> None:
    st.caption("Escolha a área que deseja acessar.")
    st.write("")

    # O ícone de cada área é desenhado pelo tema global em CSS para manter
    # o padrão visual verde, grande e consistente da referência aprovada.
    with st.container(key="sst_menu_cards"):
        cols = st.columns(3)
        for indice, (rotulo, nome, _) in enumerate(AREAS):
            with cols[indice % 3]:
                st.button(
                    rotulo,
                    key=f"sst_menu_{indice}",
                    use_container_width=True,
                    on_click=_abrir_area,
                    args=(nome,),
                )


def renderizar_modulo_sst_menu(actor: dict) -> None:
    core.aplicar_estilo_sst()
    core.renderizar_cabecalho_modulo()

    if mensagem := st.session_state.pop("sst_mensagem", None):
        core.mostrar_notificacao(mensagem)

    area_ativa = st.session_state.get("sst_area_ativa")

    _, topo2 = st.columns([6.8, 1.35])
    with topo2:
        if st.button("Ajuda / Protocolos", use_container_width=True, key="sst_ajuda_protocolos_menu"):
            core._popup_ajuda_protocolos()

    if not area_ativa:
        _render_menu()
        return

    mapa = {nome: render for _, nome, render in AREAS}
    render = mapa.get(area_ativa)
    if render is None:
        _voltar_menu()
        st.rerun()

    core._inicializar_sst_uma_vez()

    st.caption(f"Segurança do Trabalho  ›  {area_ativa}")
    if st.button("← Voltar para Segurança do Trabalho", key="sst_voltar_menu_interno"):
        _voltar_menu()
        st.rerun()

    render(actor)
