from __future__ import annotations

from pathlib import Path
import html

import streamlit as st


LOGO_PATH = Path("logo.png")


def aplicar_estilo_sst() -> None:
    """Estilo visual leve e estável para o módulo SST/EPI."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px;}
        [data-testid="stMetric"] {
            border: 1px solid rgba(49, 51, 63, 0.14);
            border-radius: 12px;
            padding: 14px 16px;
            background: rgba(255,255,255,0.72);
        }
        [data-testid="stMetricLabel"] {font-weight: 600;}
        div.stButton > button, div.stDownloadButton > button {
            border-radius: 9px;
            min-height: 2.7rem;
            font-weight: 600;
        }
        [data-testid="stExpander"] {border-radius: 10px;}
        .sst-kicker {font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; opacity: .65; font-weight: 700;}
        .sst-hero-title {font-size: 2.35rem; font-weight: 800; line-height: 1.1; margin: .2rem 0 .55rem;}
        .sst-hero-text {font-size: 1rem; opacity: .78; max-width: 760px;}
        .sst-section-note {
            border-left: 4px solid rgba(49,51,63,.35);
            padding: .7rem 1rem;
            background: rgba(49,51,63,.035);
            border-radius: 0 8px 8px 0;
            margin: .5rem 0 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_logo(width: int = 170) -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown("### COPA")
        st.caption("Soluções Sustentáveis")


def renderizar_cabecalho_modulo() -> None:
    esquerda, direita = st.columns([5, 1.2], vertical_alignment="center")
    with esquerda:
        renderizar_logo(165)
    with direita:
        st.caption("AMBIENTE INTERNO")
        st.markdown("**Segurança do Trabalho**")

    st.markdown(
        """
        <div class="sst-kicker">Gestão integrada de segurança</div>
        <div class="sst-hero-title">⛑️ SST / EPI</div>
        <div class="sst-hero-text">
        Colaboradores, controle de CA, entregas de EPI, documentos, ordens de serviço de SST
        e preparação para assinatura biométrica com rastreabilidade.
        </div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_notificacao(mensagem: object) -> None:
    """Notificação temporária nativa do Streamlit."""
    if mensagem:
        st.toast(str(mensagem), icon="✅")


def renderizar_aviso_desenvolvimento() -> None:
    st.warning("🧪 AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI")
    st.caption(
        "Esta interface é destinada aos testes do novo módulo e não substitui "
        "o sistema oficial de manutenção."
    )


def renderizar_card_texto(titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="sst-section-note"><strong>{html.escape(titulo)}</strong><br>{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )
