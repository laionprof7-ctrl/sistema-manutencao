from __future__ import annotations

import streamlit as st

from sst_ui import aplicar_estilo_sst, mostrar_notificacao, renderizar_cabecalho_modulo


AREAS = [
    ("Visão Geral", "Visão Geral", "_render_dashboard"),
    ("Colaboradores", "Colaboradores", "_render_colaboradores"),
    ("Controle de GHE", "Controle de GHE", "_render_ghes"),
    ("Gestão de Registros de EPI", "Gestão de Registros de EPI", "_render_epis"),
    ("Entrega de EPI", "Entrega de EPI", "_render_entregas"),
    ("Documentações SST", "Documentações SST", "_render_documentos"),
    ("Assinaturas de Documentos", "Assinaturas de Documentos", "_render_assinaturas"),
]


def _abrir_area(nome: str) -> None:
    st.session_state["sst_area_ativa"] = nome


def _voltar_menu() -> None:
    # Ao sair de qualquer submódulo, elimina também estados transitórios para
    # impedir que uma tela anterior seja retomada acidentalmente.
    for chave in (
        "sst_area_ativa",
        "sst_assinatura_documento",
        "sst_bio_sign_request",
        "sst_bio_enroll_request",
        "sst_bio_sign_error",
        "sst_bio_last_error",
    ):
        st.session_state.pop(chave, None)


def _render_menu() -> None:
    st.caption("Escolha a área que deseja acessar.")
    st.write("")

    # O menu inicial não importa serviços, relatórios nem integração biométrica.
    # Isso reduz o custo de simplesmente entrar no módulo SST.
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


def _carregar_core(area_ativa: str):
    import sst_app_core as core

    # Biometria só entra em memória quando a área realmente precisa dela.
    if area_ativa in ("Colaboradores", "Assinaturas de Documentos"):
        import sst_app  # noqa: F401

    return core


def _abrir_ajuda() -> None:
    import sst_app_core as core
    core._popup_ajuda_protocolos()


def renderizar_modulo_sst_menu(actor: dict) -> None:
    aplicar_estilo_sst()
    renderizar_cabecalho_modulo()

    if mensagem := st.session_state.pop("sst_mensagem", None):
        mostrar_notificacao(mensagem)

    area_ativa = st.session_state.get("sst_area_ativa")

    # Dentro de um submódulo, a navegação é hierárquica:
    # Submódulo -> menu Segurança do Trabalho -> menu principal Copa Gestão.
    # O botão externo de retorno ao Portal só aparece no menu raiz do SST.
    if area_ativa:
        st.markdown(
            """
            <style>
            .st-key-voltar_portal_sst { display: none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    _, topo2 = st.columns([6.8, 1.35])
    with topo2:
        if st.button("Ajuda / Protocolos", use_container_width=True, key="sst_ajuda_protocolos_menu"):
            _abrir_ajuda()

    if not area_ativa:
        _render_menu()
        return

    mapa = {nome: renderer_name for _, nome, renderer_name in AREAS}
    renderer_name = mapa.get(area_ativa)
    if renderer_name is None:
        _voltar_menu()
        st.rerun()

    core = _carregar_core(area_ativa)
    core._inicializar_sst_uma_vez()

    st.caption(f"Segurança do Trabalho  ›  {area_ativa}")
    if st.button("← Voltar para Segurança do Trabalho", key="sst_voltar_menu_interno"):
        _voltar_menu()
        st.rerun()

    render = getattr(core, renderer_name)
    render(actor)
