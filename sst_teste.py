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

    # Os textos dos cards ficam limpos. Os ícones são desenhados pelo mesmo CSS
    # verde usado no SST, reutilizando os sete estilos já aprovados.
    substituicoes_menu = {
        "📝 Abrir Ordem de Serviço": "Abrir Ordem de Serviço",
        "🔍 Consultar Ordens de Serviço": "Consultar Ordens de Serviço",
        "🛠️ Painel da Oficina": "Painel da Oficina",
        "🎯 Triagem e Prioridade": "Triagem e Prioridade",
        "👤 Gestão de Usuários": "Gestão de Usuários",
        "🔑 Alterar minha senha": "Alterar minha senha",
        "🧾 Auditoria": "Auditoria",
    }
    for antigo, novo in substituicoes_menu.items():
        codigo = codigo.replace(antigo, novo)

    # Menu da Manutenção em três colunas. As chaves dos botões reaproveitam os
    # mesmos desenhos do SST. O CSS local abaixo ativa o pseudo-elemento do ícone
    # também dentro do container da Manutenção.
    codigo = codigo.replace(
        '    cols = st.columns(2)\n'
        '    for i, (rotulo, destino) in enumerate(opcoes):\n'
        '        with cols[i % 2]:\n'
        '            if destino == "Logout":\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=logout_callback)\n'
        '            else:\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=navegar, args=(destino,))',
        '    st.caption("Escolha a área que deseja acessar.")\n'
        '    st.markdown("""\n'
        '    <style>\n'
        '    .st-key-manutencao_menu_cards button {\n'
        '        display:flex !important; align-items:center !important; justify-content:flex-start !important;\n'
        '        gap:1.45rem !important; text-align:left !important;\n'
        '    }\n'
        '    .st-key-manutencao_menu_cards button::before {\n'
        '        content:""; display:block; flex:0 0 76px; width:76px; height:76px;\n'
        '        background:linear-gradient(180deg,#14875b 0%,#005b46 100%);\n'
        '        -webkit-mask-position:center; mask-position:center;\n'
        '        -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat;\n'
        '        -webkit-mask-size:contain; mask-size:contain;\n'
        '    }\n'
        '    @media (max-width:900px){.st-key-manutencao_menu_cards button::before{flex-basis:58px;width:58px;height:58px}}\n'
        '    @media (max-width:768px){.st-key-manutencao_menu_cards button::before{flex-basis:44px;width:44px;height:44px}}\n'
        '    </style>\n'
        '    """, unsafe_allow_html=True)\n'
        '    icones_menu = {\n'
        '        "Abrir Chamado": 4,\n'
        '        "Consultar Chamados": 5,\n'
        '        "Oficina": 3,\n'
        '        "Triagem": 0,\n'
        '        "Usuarios": 1,\n'
        '        "Minha Senha": 2,\n'
        '        "Auditoria": 6,\n'
        '    }\n'
        '    with st.container(key="manutencao_menu_cards"):\n'
        '        cols = st.columns(3)\n'
        '        for i, (rotulo, destino) in enumerate(opcoes):\n'
        '            with cols[i % 3]:\n'
        '                icone = icones_menu.get(destino, i % 7)\n'
        '                st.button(rotulo, key=f"sst_menu_{icone}", use_container_width=True, on_click=navegar, args=(destino,))',
    )

    return compile(codigo, str(APP), "exec")


exec(_compilar_app(), {"__name__": "__main__", "__file__": str(APP)})
