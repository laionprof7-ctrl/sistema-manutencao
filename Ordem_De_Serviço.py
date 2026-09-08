import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta
from PIL import Image

# CARREGAMENTO SEGURO DA LOGO
logo_img = None
if os.path.exists("logo.png"):
    try:
        logo_img = Image.open("logo.png")
    except Exception:
        logo_img = None

# Configuração da página
st.set_page_config(
    page_title="Gestão de Manutenção - Copa Ambiental", 
    page_icon=logo_img if logo_img else "🚛", 
    layout="wide"
)

# OCULTA BARRA SUPERIOR E MENU
esconder_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    </style>
"""
st.markdown(esconder_menu, unsafe_allow_html=True)

# ARQUIVOS DE BANCO DE DADOS
ARQUIVO_CSV = 'chamados_manutencao.csv'
ARQUIVO_USUARIOS = 'usuarios.csv'

# ... (restante das funções do seu código permanece igual)
