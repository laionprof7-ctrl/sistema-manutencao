"""
Entrada estável do ambiente de desenvolvimento SST/EPI.
Carrega primeiro uma tela leve e só abre o módulo completo após ação do usuário.
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


# Rotina leve de manutenção independente da aba selecionada.
# O cron do PostgreSQL é a automação principal; isto funciona como redundância.
try:
    from sst_database import inicializar_banco_sst
    from sst_services import sincronizar_cas_vencidos
    inicializar_banco_sst()
    sincronizar_cas_vencidos()
except Exception as exc:
    st.warning(f"Rotina automática SST indisponível neste carregamento: {exc}")

if "sst_modulo_aberto" not in st.session_state:
    st.session_state["sst_modulo_aberto"] = False

if not st.session_state["sst_modulo_aberto"]:
    st.title("🦺 SST / EPI")
    st.write(
        "O módulo está pronto para ser carregado. "
        "Use o botão abaixo para entrar no ambiente de testes."
    )

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
