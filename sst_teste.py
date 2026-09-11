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

# Inicialização otimizada da Manutenção.
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

# Limpeza única dos dados operacionais usados durante o desenvolvimento.
# O marcador persistido no banco garante que reinícios futuros não apaguem
# dados reais cadastrados após a liberação do sistema.
try:
    from final_reset import aplicar_reset_final_uma_vez

    aplicar_reset_final_uma_vez()
except Exception as exc:
    # Não derruba o portal por causa da rotina de finalização. Mantemos a
    # informação na sessão para diagnóstico, sem expor detalhes ao usuário.
    st.session_state["final_reset_erro"] = str(exc)

# A pilha SST só é preparada quando o usuário realmente está no módulo.
if st.session_state.get("aba_ativa") == "SST":
    try:
        import sst_database
        from sst_fast_init import inicializar_banco_sst_rapido

        sst_database.inicializar_banco_sst = inicializar_banco_sst_rapido
    except Exception:
        pass

    # A retenção não deve atrasar a abertura do menu do SST. Ela só é verificada
    # nas áreas em que documentos/assinaturas são efetivamente consultados.
    area_sst = st.session_state.get("sst_area_ativa")
    if area_sst in {"Documentações SST", "Assinaturas de Documentos"}:
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

    # Leituras de tela reutilizam cache por 60 segundos. Ações de escrita já
    # limpam os caches imediatamente no app.py.
    codigo = codigo.replace(
        "@st.cache_data(ttl=12, show_spinner=False)",
        "@st.cache_data(ttl=60, show_spinner=False)",
    )
    codigo = codigo.replace(
        "@st.cache_data(ttl=10, show_spinner=False)",
        "@st.cache_data(ttl=60, show_spinner=False)",
    )

    # Portal principal sem emojis nos nomes dos módulos.
    codigo = codigo.replace('"🔧 Manutenção"', '"Manutenção"')
    codigo = codigo.replace('"🦺 Segurança do Trabalho"', '"Segurança do Trabalho"')

    # O SST usa o menu modular otimizado.
    codigo = codigo.replace(
        "from sst_app import renderizar_modulo_sst",
        "from sst_entry import renderizar_modulo_sst",
    )

    # Ao entrar novamente no SST, sempre começa pelo menu do módulo. Ao sair
    # para o Portal também limpamos qualquer subárea antiga da sessão.
    codigo = codigo.replace(
        'def navegar(destino: str):\n    st.session_state.aba_ativa = destino',
        'def navegar(destino: str):\n'
        '    atual = st.session_state.get("aba_ativa")\n'
        '    if destino == "Portal" or (destino == "SST" and atual != "SST"):\n'
        '        st.session_state.pop("sst_area_ativa", None)\n'
        '        st.session_state.pop("sst_assinatura_documento", None)\n'
        '        st.session_state.pop("sst_bio_sign_request", None)\n'
        '    st.session_state.aba_ativa = destino',
    )

    # Portal: substitui o título textual pela logo centralizada.
    codigo = codigo.replace(
        'if aba == "Portal":\n'
        '    st.title("Copa Gestão")\n'
        '    st.caption(f"Bem-vindo, {user_data[\'nome\']}. Escolha o módulo que deseja acessar.")',
        'if aba == "Portal":\n'
        '    if logo_img:\n'
        '        _, logo_col, _ = st.columns([1, 0.58, 1])\n'
        '        with logo_col:\n'
        '            st.image(logo_img, use_container_width=True)\n'
        '    st.caption(f"Bem-vindo, {user_data[\'nome\']}. Escolha o módulo que deseja acessar.")',
    )

    # Logout discreto no fim do Portal principal.
    codigo = codigo.replace(
        '        st.caption("GHE, colaboradores, EPIs, entregas, documentos e assinaturas.")\n'
        '    st.stop()',
        '        st.caption("GHE, colaboradores, EPIs, entregas, documentos e assinaturas.")\n'
        '    st.write("")\n'
        '    st.divider()\n'
        '    _, sair_col, _ = st.columns([1, 0.42, 1])\n'
        '    with sair_col:\n'
        '        st.button("Sair / Logout", use_container_width=True, on_click=logout_callback, key="portal_logout")\n'
        '    st.stop()',
        1,
    )

    # No menu do SST existe retorno ao Portal. Dentro de um submódulo o retorno
    # correto é apenas para o menu de Segurança do Trabalho.
    codigo = codigo.replace(
        '    if st.button("← Voltar ao menu principal", use_container_width=False, key="voltar_portal_sst"):\n'
        '        navegar("Portal")\n'
        '        st.rerun()',
        '    if not st.session_state.get("sst_area_ativa"):\n'
        '        if st.button("← Voltar ao menu principal", use_container_width=False, key="voltar_portal_sst"):\n'
        '            navegar("Portal")\n'
        '            st.rerun()',
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

    # Textos dos cards da Manutenção sem emoji; os ícones são desenhados no CSS.
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

    # Menu da Manutenção em três colunas e com os mesmos ícones do padrão SST.
    codigo = codigo.replace(
        '    cols = st.columns(2)\n'
        '    for i, (rotulo, destino) in enumerate(opcoes):\n'
        '        with cols[i % 2]:\n'
        '            if destino == "Logout":\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=logout_callback)\n'
        '            else:\n'
        '                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=navegar, args=(destino,))',
        '    st.caption("Escolha a área que deseja acessar.")\n'
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
