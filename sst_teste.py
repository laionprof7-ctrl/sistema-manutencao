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

# Limpeza de retenção somente quando o usuário entra no SST e, no máximo,
# uma vez por hora por sessão. Isso evita trabalho de banco no login/Manutenção.
if st.session_state.get("aba_ativa") == "SST":
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
            # A retenção nunca deve impedir o acesso ao portal.
            st.session_state["sst_retencao_verificada_em"] = agora

APP = Path(__file__).with_name("app.py")

if not APP.exists():
    raise FileNotFoundError("app.py não encontrado ao lado de sst_teste.py")

codigo = APP.read_text(encoding="utf-8")
exec(compile(codigo, str(APP), "exec"), {"__name__": "__main__", "__file__": str(APP)})
