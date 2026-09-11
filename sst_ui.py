from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import html

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo.png"


@lru_cache(maxsize=1)
def _logo_bytes() -> bytes | None:
    try:
        return LOGO_PATH.read_bytes() if LOGO_PATH.exists() else None
    except Exception:
        return None


def aplicar_estilo_sst() -> None:
    """Identidade visual central do portal de Segurança do Trabalho."""
    st.markdown(
        """
        <style>
        :root {
            --copa-green: #087b4f;
            --copa-green-dark: #075f3f;
            --copa-orange: #ef8d2d;
            --copa-ink: #1f2937;
            --copa-muted: #5f6f69;
            --copa-line: #e5e7eb;
            --copa-soft: #f7faf8;
        }

        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 3rem;
            max-width: 1540px;
        }
        header[data-testid="stHeader"] { background: transparent; }

        .block-container p,
        .block-container label,
        .block-container [data-testid="stCaptionContainer"],
        .block-container [data-testid="stMarkdownContainer"] p {
            font-size: 1.11rem !important;
            line-height: 1.56 !important;
        }
        .block-container h2 { font-size: 1.88rem !important; }
        .block-container h3 { font-size: 1.6rem !important; }
        .block-container h4 { font-size: 1.28rem !important; }

        [data-testid="stRadio"] label p {
            font-size: 1.1rem !important;
            font-weight: 675 !important;
        }
        [data-testid="stRadio"] > div { gap: .55rem .95rem !important; }

        .stSelectbox label,
        .stTextInput label,
        .stNumberInput label,
        .stDateInput label,
        .stTextArea label,
        .stCheckbox label {
            font-size: 1.07rem !important;
            font-weight: 650 !important;
        }
        .stSelectbox [data-baseweb="select"] > div,
        .stTextInput input,
        .stNumberInput input,
        .stDateInput input,
        .stTextArea textarea {
            font-size: 1.1rem !important;
        }

        [data-testid="stMetric"] {
            border: 1px solid var(--copa-line);
            border-radius: 16px;
            padding: 19px 21px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15,23,42,.04);
            min-height: 120px;
        }
        [data-testid="stMetricLabel"] { font-weight: 700; color: var(--copa-muted); font-size: 1.08rem !important; }
        [data-testid="stMetricValue"] { font-weight: 800; color: var(--copa-ink); font-size: 2.12rem !important; }

        div.stButton > button,
        div.stDownloadButton > button,
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-secondary"] {
            border-radius: 11px !important;
            min-height: 3rem;
            font-size: 1.06rem !important;
            font-weight: 700 !important;
        }
        div.stButton > button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background: var(--copa-green) !important;
            border-color: var(--copa-green) !important;
            color: #ffffff !important;
        }
        div.stButton > button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: var(--copa-green-dark) !important;
            border-color: var(--copa-green-dark) !important;
        }

        [data-testid="stExpander"] { border-radius: 12px; overflow: hidden; }
        [data-testid="stExpander"] summary p { font-size: 1.1rem !important; font-weight: 650 !important; }

        table.sst-table { font-size: 1.09rem !important; }
        table.sst-table th, table.sst-table td { padding: 13px 15px !important; }

        .sst-brand-tag {
            font-size: .88rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            color: var(--copa-muted);
            font-weight: 800;
            margin-bottom: 4px;
        }
        .sst-brand-title { color: var(--copa-ink); font-size: 1.16rem; font-weight: 800; }
        .sst-section-note { border-left: 4px solid var(--copa-green); padding: .85rem 1.05rem; background: rgba(8,123,79,.045); border-radius: 0 10px 10px 0; margin: .5rem 0 1rem; }
        .sst-dev-note { border: 1px solid #f2df8c; background: #fffbea; color: #846300; padding: 12px 16px; border-radius: 12px; margin-bottom: 10px; font-size: 1rem; }

        @media (max-width: 768px) {
            .block-container p,
            .block-container label,
            .block-container [data-testid="stMarkdownContainer"] p { font-size: 1rem !important; }
            [data-testid="stRadio"] label p { font-size: 1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_logo(width: int = 180) -> None:
    logo = _logo_bytes()
    if logo:
        st.image(logo, width=width)
    else:
        st.markdown("### COPA")
        st.caption("Soluções Sustentáveis")


def renderizar_topo_portal() -> None:
    esquerda, direita = st.columns([4.5, 1.5], vertical_alignment="center")
    with esquerda:
        renderizar_logo(235)
    with direita:
        st.markdown('<div style="text-align:right"><div class="sst-brand-tag">Copa Gestão</div><div class="sst-brand-title">Segurança do Trabalho</div></div>', unsafe_allow_html=True)


def renderizar_portal_inicial() -> None:
    st.markdown("## Segurança do Trabalho")


def renderizar_cabecalho_modulo() -> None:
    """Cabeçalho interno enxuto do módulo."""
    esquerda, direita = st.columns([5, 1.35], vertical_alignment="center")
    with esquerda:
        renderizar_logo(220)
    with direita:
        st.caption("COPA GESTÃO")
        st.markdown("**Segurança do Trabalho**")
    st.markdown("### Segurança do Trabalho")


def mostrar_notificacao(mensagem: object) -> None:
    if mensagem:
        st.toast(str(mensagem), icon="✅")


def renderizar_aviso_desenvolvimento() -> None:
    st.markdown('<div class="sst-dev-note"><strong>AMBIENTE DE DESENVOLVIMENTO — SEGURANÇA DO TRABALHO</strong></div>', unsafe_allow_html=True)


def renderizar_card_texto(titulo: str, texto: str) -> None:
    st.markdown(f'<div class="sst-section-note"><strong>{html.escape(titulo)}</strong><br>{html.escape(texto)}</div>', unsafe_allow_html=True)
