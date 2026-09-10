from __future__ import annotations

from pathlib import Path
import html

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo.png"


def aplicar_estilo_sst() -> None:
    """Aplica apenas CSS simples e estável; evita HTML complexo no layout."""
    st.markdown(
        """
<style>
:root {
  --copa-green: #087b4f;
  --copa-green-dark: #075f3f;
  --copa-orange: #ef8d2d;
  --copa-ink: #1f2937;
  --copa-muted: #6b7280;
  --copa-line: #e5e7eb;
}

.block-container {
  padding-top: 1.35rem;
  padding-bottom: 3rem;
  max-width: 1540px;
}

header[data-testid="stHeader"] { background: transparent; }

[data-testid="stMetric"] {
  border: 1px solid var(--copa-line);
  border-radius: 16px;
  padding: 18px 20px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  min-height: 116px;
}
[data-testid="stMetricLabel"] { font-weight: 700; color: var(--copa-muted); }
[data-testid="stMetricValue"] { font-weight: 800; color: var(--copa-ink); }

/* Botões: compatível com seletores antigos e atuais do Streamlit. */
div.stButton > button,
div.stDownloadButton > button,
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-secondary"] {
  border-radius: 11px !important;
  min-height: 2.8rem;
  font-weight: 700 !important;
}

div.stButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
  background: var(--copa-green) !important;
  border-color: var(--copa-green) !important;
  color: white !important;
}
div.stButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
  background: var(--copa-green-dark) !important;
  border-color: var(--copa-green-dark) !important;
}

[data-testid="stExpander"] { border-radius: 12px; overflow: hidden; }

.sst-brand-tag {
  font-size: .76rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--copa-muted);
  font-weight: 800;
  margin-bottom: 3px;
}
.sst-brand-title { color: var(--copa-ink); font-size: 1rem; font-weight: 800; }
.sst-kicker {
  font-size: .76rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--copa-green);
  font-weight: 800;
  margin-bottom: 2px;
}
.sst-subtle { color: var(--copa-muted); line-height: 1.55; }
.sst-portal-box {
  border: 1px solid var(--copa-line);
  border-radius: 18px;
  padding: 22px 24px;
  background: #ffffff;
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.055);
  margin: 10px 0 16px;
}
.sst-pill {
  display: inline-block;
  padding: 7px 14px;
  border: 1px solid #d7e7df;
  border-radius: 999px;
  background: #f7fbf9;
  color: var(--copa-green-dark);
  font-size: .82rem;
  font-weight: 800;
}
.sst-section-note {
  border-left: 4px solid var(--copa-green);
  padding: .8rem 1rem;
  background: rgba(8,123,79,.045);
  border-radius: 0 10px 10px 0;
  margin: .5rem 0 1rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_logo(width: int = 180) -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown("### COPA")
        st.caption("Soluções Sustentáveis")


def _marca_direita(texto: str) -> None:
    st.markdown(
        f'<div style="text-align:right"><div class="sst-brand-tag">COPA GESTÃO</div>'
        f'<div class="sst-brand-title">{html.escape(texto)}</div></div>',
        unsafe_allow_html=True,
    )


def renderizar_topo_portal() -> None:
    esquerda, direita = st.columns([4.5, 1.5], vertical_alignment="center")
    with esquerda:
        renderizar_logo(190)
    with direita:
        _marca_direita("Segurança do Trabalho")


def renderizar_portal_inicial() -> None:
    """Tela inicial usando componentes nativos para evitar HTML cru na página."""
    renderizar_topo_portal()
    st.write("")

    icone, conteudo = st.columns([0.65, 8.35], vertical_alignment="center")
    with icone:
        st.markdown("# 🦺")
    with conteudo:
        st.markdown("<div class='sst-kicker'>Segurança, controle e rastreabilidade</div>", unsafe_allow_html=True)
        st.markdown("# SST / EPI")
        st.markdown(
            "<div class='sst-subtle'>Gestão integrada de colaboradores, EPIs, entregas, documentos e preparação "
            "do fluxo de assinatura biométrica, com histórico e rastreabilidade.</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Módulo**")
        st.caption("SST / EPI")
    with c2:
        st.markdown("**Ambiente**")
        st.caption("🟢 Desenvolvimento")
    with c3:
        st.markdown("**Rastreabilidade**")
        st.caption("🟢 Ativa")


def renderizar_cabecalho_modulo() -> None:
    """Cabeçalho interno sem interpolar SVG/HTML multilinha."""
    esquerda, direita = st.columns([5, 1.3], vertical_alignment="center")
    with esquerda:
        renderizar_logo(160)
    with direita:
        _marca_direita("Segurança do Trabalho")

    st.write("")
    icone, titulo = st.columns([0.55, 8.45], vertical_alignment="center")
    with icone:
        st.markdown("## 🦺")
    with titulo:
        st.markdown("<div class='sst-kicker'>Gestão integrada de segurança</div>", unsafe_allow_html=True)
        st.markdown("## SST / EPI")

    st.markdown(
        "<div class='sst-subtle'>Colaboradores, controle de CA, entregas de EPI, documentos, ordens de serviço "
        "de SST e preparação para assinatura biométrica com rastreabilidade.</div>",
        unsafe_allow_html=True,
    )


def mostrar_notificacao(mensagem: object) -> None:
    if mensagem:
        st.toast(str(mensagem), icon="✅")


def renderizar_aviso_desenvolvimento() -> None:
    st.warning("🧪 AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI")
    st.caption("Área destinada a testes. Não substitui o sistema oficial de manutenção.")


def renderizar_card_texto(titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="sst-section-note"><strong>{html.escape(titulo)}</strong><br>{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )
