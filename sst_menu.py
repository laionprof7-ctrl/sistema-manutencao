from __future__ import annotations

import streamlit as st

import sst_app_core as core


AREAS = [
    ("Visão Geral", "Indicadores, pendências e alertas importantes.", core._render_dashboard),
    ("Colaboradores", "Cadastro, situação, GHE e biometria dos colaboradores.", core._render_colaboradores),
    ("GHE", "Grupos homogêneos, riscos, medidas, funções e setores.", core._render_ghes),
    ("EPIs", "Cadastro, CA, validade e situação dos equipamentos.", core._render_epis),
    ("Entrega de EPI", "Nova entrega e histórico das entregas realizadas.", core._render_entregas),
    ("Documentos e OS SST", "Ordens de Serviço, documentos gerados e PDFs.", core._render_documentos),
    ("Assinaturas", "Documentos que aguardam confirmação biométrica.", core._render_assinaturas),
]


def _abrir_area(nome: str) -> None:
    st.session_state["sst_area_ativa"] = nome


def _voltar_menu() -> None:
    st.session_state.pop("sst_area_ativa", None)
    st.session_state.pop("sst_assinatura_documento", None)


def _render_menu() -> None:
    st.markdown("## Segurança do Trabalho")
    st.caption("Escolha a área que deseja acessar.")
    st.write("")

    cols = st.columns(2)
    for indice, (nome, descricao, _) in enumerate(AREAS):
        with cols[indice % 2]:
            with st.container(border=True):
                st.markdown(f"### {nome}")
                st.caption(descricao)
                st.button(
                    f"Acessar {nome}",
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

    topo1, topo2 = st.columns([6.8, 1.35])
    with topo2:
        if st.button("Ajuda / Protocolos", use_container_width=True, key="sst_ajuda_protocolos_menu"):
            core._popup_ajuda_protocolos()

    if not area_ativa:
        _render_menu()
        return

    mapa = {nome: render for nome, _, render in AREAS}
    render = mapa.get(area_ativa)
    if render is None:
        _voltar_menu()
        st.rerun()

    # A preparação do banco só é necessária ao entrar numa área operacional.
    # O menu inicial permanece leve e não dispara consultas de negócio.
    core._inicializar_sst_uma_vez()

    st.caption(f"Segurança do Trabalho  ›  {area_ativa}")
    if st.button("← Voltar para Segurança do Trabalho", key="sst_voltar_menu_interno"):
        _voltar_menu()
        st.rerun()

    render(actor)
