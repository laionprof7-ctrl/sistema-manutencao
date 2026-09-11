"""
Entrada do ambiente de desenvolvimento.

O Streamlit Community Cloud ainda inicia este arquivo na branch
desenvolvimento-sst. Para evitar dois portais concorrentes, este arquivo
executa o app.py completo (Copa Gestão), que passa a ser a única fonte
da navegação, autenticação e controle de sessão.
"""

from pathlib import Path

from copa_brand import instalar_tema_apos_page_config

instalar_tema_apos_page_config()

APP = Path(__file__).with_name("app.py")

if not APP.exists():
    raise FileNotFoundError("app.py não encontrado ao lado de sst_teste.py")

codigo = APP.read_text(encoding="utf-8")
exec(compile(codigo, str(APP), "exec"), {"__name__": "__main__", "__file__": str(APP)})
