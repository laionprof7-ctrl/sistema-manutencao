import streamlit as st
import traceback
import time

st.set_page_config(
    page_title="Diagnóstico SST/EPI",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 Diagnóstico do módulo SST/EPI")
st.info("Se esta tela apareceu, o Streamlit e o arquivo sst_teste.py estão executando.")

def etapa(nome):
    st.write(f"✅ {nome}")
    st.flush() if hasattr(st, "flush") else None

try:
    etapa("1. Streamlit iniciou")

    with st.spinner("2. Importando sst_database..."):
        import sst_database
    etapa("2. sst_database importado")

    with st.spinner("3. Inicializando/migrando banco SST..."):
        sst_database.inicializar_banco_sst()
    etapa("3. Banco SST inicializado")

    with st.spinner("4. Importando sst_services..."):
        import sst_services
    etapa("4. sst_services importado")

    with st.spinner("5. Importando sst_reports..."):
        import sst_reports
    etapa("5. sst_reports importado")

    with st.spinner("6. Importando sst_app..."):
        from sst_app import renderizar_modulo_sst
    etapa("6. sst_app importado")

    st.success("Todos os componentes carregaram. O problema não está nos imports/migração.")

    if st.button("Abrir módulo SST agora", type="primary"):
        actor_teste = {
            "usuario": "admin",
            "nome": "Ambiente de Desenvolvimento",
            "nivel": 4.0,
        }
        renderizar_modulo_sst(actor_teste)

except Exception as exc:
    st.error(f"ERRO: {type(exc).__name__}: {exc}")
    st.code(traceback.format_exc())
