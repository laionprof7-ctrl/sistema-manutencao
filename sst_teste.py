"""
Entrada do ambiente de desenvolvimento.

O Streamlit Community Cloud ainda inicia este arquivo na branch
desenvolvimento-sst. Para evitar dois portais concorrentes, este arquivo
executa o app.py completo (Copa Gestão), que passa a ser a única fonte
da navegação, autenticação e controle de sessão.
"""

import time
from pathlib import Path

import streamlit as st

from copa_brand import instalar_tema_apos_page_config

instalar_tema_apos_page_config()

# A Manutenção usa uma inicialização rápida quando o schema já está pronto e
# limita a verificação automática de OS expiradas. Isso evita consultas e
# introspecções repetidas durante a navegação normal.
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

# Não carregamos a pilha SST no login, Portal ou Manutenção. Ela só entra
# na memória quando o usuário realmente abre Segurança do Trabalho.
if st.session_state.get("aba_ativa") == "SST":
    try:
        import sst_database
        from sst_fast_init import inicializar_banco_sst_rapido

        sst_database.inicializar_banco_sst = inicializar_banco_sst_rapido
    except Exception:
        pass

    # Limpeza de retenção no máximo uma vez por hora por sessão.
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

codigo = APP.read_text(encoding="utf-8")

# Mantém os dados de leitura da Manutenção em memória por mais tempo.
# Toda operação de escrita já limpa esses caches explicitamente.
codigo = codigo.replace("@st.cache_data(ttl=12, show_spinner=False)", "@st.cache_data(ttl=30, show_spinner=False)")
codigo = codigo.replace("@st.cache_data(ttl=10, show_spinner=False)", "@st.cache_data(ttl=30, show_spinner=False)")

# Os nomes dos módulos ficam limpos, sem símbolos, tanto no portal quanto
# na barra lateral. Mantemos os demais ícones apenas onde ajudam a operação.
codigo = codigo.replace('"🔧 Manutenção"', '"Manutenção"')
codigo = codigo.replace('"🦺 Segurança do Trabalho"', '"Segurança do Trabalho"')

# A Manutenção agora é um módulo do Copa Gestão, portanto segue a mesma
# navegação do SST: volta ao portal e não oferece logout dentro do módulo.
codigo = codigo.replace(
    '    st.caption("Copa Gestão  ›  Manutenção  ›  Ordens de Serviço")\n'
    '    st.title("Ordens de Serviço")',
    '    st.caption("Copa Gestão  ›  Manutenção  ›  Ordens de Serviço")\n\n'
    '    if st.button("← Voltar ao menu principal", use_container_width=False, key="voltar_portal_manutencao"):\n'
    '        navegar("Portal")\n'
    '        st.rerun()\n\n'
    '    st.title("Ordens de Serviço")',
)
codigo = codigo.replace(
    '    # Navegação principal também fica no corpo da página para funcionar bem no celular,\n'
    '    # onde a barra lateral do Streamlit pode ficar recolhida/oculta.\n'
    '    opcoes.append(("🚪 Sair / Logout", "Logout"))\n\n',
    '',
)

exec(compile(codigo, str(APP), "exec"), {"__name__": "__main__", "__file__": str(APP)})
