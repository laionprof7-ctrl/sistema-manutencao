from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_PATH = BASE_DIR / "assets" / "copa_background.webp"


def _background_data_uri() -> str:
    if not BACKGROUND_PATH.exists():
        return ""
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{encoded}"


def aplicar_tema_global() -> None:
    """Aplica a identidade visual da Copa a todo o portal sem alterar regras de negócio."""
    bg = _background_data_uri()
    bg_css = f"background-image: linear-gradient(rgba(0, 61, 49, .50), rgba(0, 61, 49, .50)), url('{bg}');" if bg else "background:#004d3e;"

    st.markdown(
        f"""
        <style>
        :root {{
            --copa-green: #087b4f;
            --copa-green-dark: #005b46;
            --copa-green-deep: #003d31;
            --copa-orange: #ef8d2d;
            --copa-ink: #17332b;
            --copa-muted: #64756f;
            --copa-line: rgba(8, 123, 79, .14);
            --copa-surface: rgba(255,255,255,.965);
        }}

        html, body, [data-testid="stAppViewContainer"], .stApp {{ min-height:100%; }}
        [data-testid="stAppViewContainer"] {{
            {bg_css}
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        [data-testid="stAppViewContainer"] > .main {{ background: transparent; }}

        .block-container {{
            max-width: 1480px !important;
            margin-top: 1rem;
            margin-bottom: 1.5rem;
            padding: 1.6rem 2rem 2.4rem !important;
            background: var(--copa-surface);
            border: 1px solid rgba(255,255,255,.65);
            border-radius: 24px;
            box-shadow: 0 22px 60px rgba(0, 42, 34, .20);
            backdrop-filter: blur(4px);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            background: rgba(250,253,251,.975);
            border-right: 1px solid var(--copa-line);
        }}
        [data-testid="stSidebar"] img {{
            max-width: 190px;
            margin: .3rem auto 1rem;
        }}

        h1, h2, h3 {{ color: var(--copa-ink) !important; letter-spacing: -.025em; }}
        h1 {{ font-weight: 800 !important; }}
        h2, h3 {{ font-weight: 750 !important; }}
        p, label, .stCaption {{ color: #405950; }}

        div.stButton > button,
        div.stDownloadButton > button {{
            border-radius: 12px !important;
            min-height: 46px;
            font-size: .98rem !important;
            font-weight: 750 !important;
            border: 1px solid rgba(8,123,79,.20) !important;
            transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
        }}
        div.stButton > button:hover,
        div.stDownloadButton > button:hover {{
            border-color: var(--copa-green) !important;
            transform: translateY(-1px);
            box-shadow: 0 7px 18px rgba(8,123,79,.13);
        }}
        button[data-testid="stBaseButton-primary"],
        div.stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, var(--copa-green), var(--copa-green-dark)) !important;
            color: #ffffff !important;
            border-color: transparent !important;
        }}
        button[data-testid="stBaseButton-primary"] *,
        div.stButton > button[kind="primary"] *,
        button[data-testid="stBaseButton-primary"] p,
        div.stButton > button[kind="primary"] p {{
            color: #ffffff !important;
            opacity: 1 !important;
            font-weight: 800 !important;
        }}

        [data-testid="stMetric"] {{
            background: linear-gradient(180deg, #fff, #fbfdfc);
            border: 1px solid var(--copa-line) !important;
            border-radius: 16px !important;
            padding: 14px 16px !important;
            box-shadow: 0 7px 18px rgba(0,61,49,.055);
        }}
        [data-testid="stMetricValue"] {{ color: var(--copa-green-dark) !important; font-weight: 800 !important; }}

        [data-testid="stExpander"],
        [data-testid="stForm"] {{
            border-color: var(--copa-line) !important;
            border-radius: 14px !important;
            background: rgba(255,255,255,.76);
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--copa-line);
            border-radius: 13px;
            overflow: hidden;
        }}

        .stTextInput input, .stNumberInput input, .stTextArea textarea,
        [data-baseweb="select"] > div {{
            border-radius: 10px !important;
        }}
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
            border-color: var(--copa-green) !important;
            box-shadow: 0 0 0 1px var(--copa-green) !important;
        }}

        [data-testid="stAlert"] {{ border-radius: 12px; }}
        hr {{ border-color: var(--copa-line) !important; }}

        @media (max-width: 768px) {{
            [data-testid="stAppViewContainer"] {{ background-attachment: scroll; }}
            .block-container {{
                margin: .35rem;
                padding: 1rem .85rem 1.6rem !important;
                border-radius: 18px;
            }}
            h1 {{ font-size: 1.85rem !important; }}
            h2 {{ font-size: 1.45rem !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def instalar_tema_apos_page_config() -> None:
    """No entrypoint legado, injeta o tema logo após o set_page_config do app.py."""
    if getattr(st.set_page_config, "_copa_wrapped", False):
        return

    original = st.set_page_config

    def wrapped(*args, **kwargs):
        resultado = original(*args, **kwargs)
        aplicar_tema_global()
        return resultado

    wrapped._copa_wrapped = True  # type: ignore[attr-defined]
    st.set_page_config = wrapped
