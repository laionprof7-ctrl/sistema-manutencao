"""
Entrada do ambiente de desenvolvimento.

O Streamlit Community Cloud inicia este arquivo na branch desenvolvimento-sst.
O app.py continua sendo a fonte única de autenticação, sessão e navegação.
"""

import time
from pathlib import Path

import streamlit as st

from copa_brand import instalar_tema_apos_page_config

instalar_tema_apos_page_config()

# A Manutenção usa inicialização rápida e limita verificações automáticas
# repetitivas durante a navegação normal.
try:
    import database
    from manutencao_fast_init import (
        arquivar_chamados_expirados_rapido,
        inicializar_banco_rapido,
    )

    database.inicializar_banco = inicializar_banco_rapido
    database.arquivar_chamados_expirados = arquivar_chamados_expirados_rapido
except Exception:
    pass

# A pilha SST só é carregada quando o usuário realmente abre o módulo.
if st.session_state.get("aba_ativa") == "SST":
    try:
        import sst_database
        from sst_fast_init import inicializar_banco_sst_rapido

        sst_database.inicializar_banco_sst = inicializar_banco_sst_rapido
    except Exception:
        pass

    agora = time.time()
    ultima = float(st.session_state.get("sst_retencao_verificada_em", 0.0))
    if agora - ultima >= 3600:
        try:
            from sst_retencao import limpar_documentos_sem_assinatura_expirados

            resultado = limpar_documentos_sem_assinatura_expirados()
            st.session_state["sst_retencao_verificada_em"] = agora
            if resultado.get("removidos"):
                st.session_state["sst_mensagem"] = (
                    f"{resultado['removidos']} documento(s) sem assinatura há 7 dias "
                    "foram removidos automaticamente."
                )
        except Exception:
            st.session_state["sst_retencao_verificada_em"] = agora

APP = Path(__file__).with_name("app.py")

if not APP.exists():
    raise FileNotFoundError("app.py não encontrado ao lado de sst_teste.py")


@st.cache_resource(show_spinner=False)
def _compilar_app():
    """Lê, ajusta e compila app.py uma única vez por processo/deploy."""
    codigo = APP.read_text(encoding="utf-8")

    codigo = codigo.replace(
        "@st.cache_data(ttl=12, show_spinner=False)",
        "@st.cache_data(ttl=60, show_spinner=False)",
    )
    codigo = codigo.replace(
        "@st.cache_data(ttl=10, show_spinner=False)",
        "@st.cache_data(ttl=60, show_spinner=False)",
    )

    codigo = codigo.replace('"🔧 Manutenção"', '"Manutenção"')
    codigo = codigo.replace('"🦺 Segurança do Trabalho"', '"Segurança do Trabalho"')

    # No ambiente de desenvolvimento, o SST usa o novo menu modular.
    codigo = codigo.replace(
        "from sst_app import renderizar_modulo_sst",
        "from sst_entry import renderizar_modulo_sst",
    )

    # A Manutenção é um módulo do Copa Gestão: volta ao portal e não exibe logout interno.
    codigo = codigo.replace(
        '    st.caption("Copa Gestão  ›  Manutenção  ›  Ordens de Serviço")\n'
        '    st.title("Ordens de Serviço")',
        '    st.caption("Copa Gestão  ›  Manutenção")\n\n'
        '    if st.button("← Voltar ao menu principal", use_container_width=False, key="voltar_portal_manutencao"):\n'
        '        navegar("Portal")\n'
        '        st.rerun()\n\n'
        '    st.title("Manutenção")',
    )
    codigo = codigo.replace(
        '    # Navegação principal também fica no corpo da página para funcionar bem no celular,\n'
        '    # onde a barra lateral do Streamlit pode ficar recolhida/oculta.\n'
        '    opcoes.append(("🚪 Sair / Logout", "Logout"))\n\n',
        '',
    )

    # Menu da Manutenção no mesmo padrão visual do SST: cards grandes em três colunas.
    codigo = codigo.replace(
        '    cols = st.columns(2)\n'
        '    for i, (rotulo, destino) in enumerate(opcoes):\n'
        '        with cols[i % 2]:\n'
        '            if destino == "Logout":\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=logout_callback)\n'
        '            else:\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=navegar, args=(destino,))',
        '    st.caption("Escolha a área que deseja acessar.")\n'
        '    with st.container(key="manutencao_menu_cards"):\n'
        '        cols = st.columns(3)\n'
        '        for i, (rotulo, destino) in enumerate(opcoes):\n'
        '            with cols[i % 3]:\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=navegar, args=(destino,))',
    )

    return compile(codigo, str(APP), "exec")


exec(_compilar_app(), {"__name__": "__main__", "__file__": str(APP)})
