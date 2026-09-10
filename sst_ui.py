from __future__ import annotations

from pathlib import Path
import html

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo.png"


def aplicar_estilo_sst() -> None:
    """Identidade visual central do portal SST/EPI."""
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
            --copa-soft: #f7faf8;
        }

        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 3rem;
            max-width: 1540px;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stMetric"] {
            border: 1px solid var(--copa-line);
            border-radius: 16px;
            padding: 18px 20px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            min-height: 116px;
        }

        [data-testid="stMetricLabel"] {
            font-weight: 700;
            color: var(--copa-muted);
        }

        [data-testid="stMetricValue"] {
            font-weight: 800;
            color: var(--copa-ink);
        }

        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 11px;
            min-height: 2.8rem;
            font-weight: 700;
        }

        div.stButton > button[kind="primary"] {
            background: var(--copa-green);
            border-color: var(--copa-green);
        }

        div.stButton > button[kind="primary"]:hover {
            background: var(--copa-green-dark);
            border-color: var(--copa-green-dark);
        }

        [data-testid="stExpander"] {
            border-radius: 12px;
            overflow: hidden;
        }

        .sst-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            padding: 8px 2px 18px;
            border-bottom: 1px solid var(--copa-line);
            margin-bottom: 24px;
        }

        .sst-brand-tag {
            font-size: .76rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            color: var(--copa-muted);
            font-weight: 800;
            margin-bottom: 3px;
        }

        .sst-brand-title {
            color: var(--copa-ink);
            font-size: 1rem;
            font-weight: 800;
        }

        .sst-portal-shell {
            max-width: 1080px;
            margin: 0 auto;
        }

        .sst-portal-card {
            border: 1px solid var(--copa-line);
            border-radius: 22px;
            background:
                radial-gradient(circle at top right, rgba(8,123,79,.08), transparent 34%),
                #ffffff;
            box-shadow: 0 20px 60px rgba(15, 23, 42, 0.07);
            padding: 38px 42px 34px;
            margin-top: 8px;
        }

        .sst-hero-row {
            display: flex;
            align-items: center;
            gap: 22px;
            margin-bottom: 12px;
        }

        .sst-hardhat {
            width: 78px;
            height: 78px;
            flex: 0 0 78px;
            display: grid;
            place-items: center;
            border-radius: 20px;
            background: linear-gradient(145deg, rgba(239,141,45,.16), rgba(8,123,79,.08));
            border: 1px solid rgba(239,141,45,.25);
        }

        .sst-kicker {
            font-size: .76rem;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: var(--copa-green);
            font-weight: 800;
            margin-bottom: 4px;
        }

        .sst-hero-title {
            font-size: 2.65rem;
            font-weight: 850;
            line-height: 1.04;
            color: var(--copa-ink);
            margin: 0 0 7px 0;
        }

        .sst-hero-text {
            font-size: 1.03rem;
            line-height: 1.65;
            color: var(--copa-muted);
            max-width: 790px;
        }

        .sst-feature-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0,1fr));
            gap: 14px;
            margin: 28px 0 26px;
        }

        .sst-feature {
            border: 1px solid var(--copa-line);
            border-radius: 14px;
            padding: 16px 18px;
            background: rgba(247,250,248,.78);
        }

        .sst-feature-label {
            font-size: .73rem;
            color: var(--copa-muted);
            text-transform: uppercase;
            letter-spacing: .06em;
            font-weight: 800;
            margin-bottom: 4px;
        }

        .sst-feature-value {
            font-size: 1.05rem;
            color: var(--copa-ink);
            font-weight: 800;
            white-space: normal;
        }

        .sst-status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--copa-green);
            margin-right: 7px;
            box-shadow: 0 0 0 4px rgba(8,123,79,.10);
        }

        .sst-module-line {
            text-align: center;
            color: var(--copa-muted);
            font-size: .86rem;
            margin-top: 12px;
            line-height: 1.5;
        }

        .sst-section-note {
            border-left: 4px solid var(--copa-green);
            padding: .8rem 1rem;
            background: rgba(8,123,79,.045);
            border-radius: 0 10px 10px 0;
            margin: .5rem 0 1rem;
        }

        .sst-dev-note {
            border: 1px solid #f2df8c;
            background: #fffbea;
            color: #846300;
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 10px;
            font-size: .92rem;
        }

        @media (max-width: 900px) {
            .sst-portal-card { padding: 28px 24px; }
            .sst-feature-strip { grid-template-columns: 1fr; }
            .sst-hero-title { font-size: 2.15rem; }
            .sst-hardhat { width: 66px; height: 66px; flex-basis: 66px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hardhat_svg() -> str:
    """Capacete de segurança industrial vetorial, sem depender de arquivo externo."""
    return """
    <svg width="52" height="52" viewBox="0 0 64 64" aria-label="Capacete de segurança" role="img">
      <path d="M15 37c0-12 7-21 17-23v12h4V14c10 2 17 11 17 23"
            fill="#f5a623" stroke="#1f2937" stroke-width="3" stroke-linejoin="round"/>
      <path d="M11 38c0-2 2-4 4-4h34c2 0 4 2 4 4v2H11v-2z"
            fill="#f5a623" stroke="#1f2937" stroke-width="3"/>
      <path d="M8 41h48c0 6-5 9-12 9H20C13 50 8 47 8 41z"
            fill="#ffffff" stroke="#1f2937" stroke-width="3" stroke-linejoin="round"/>
      <path d="M24 17v10M40 17v10" stroke="#1f2937" stroke-width="3" stroke-linecap="round"/>
    </svg>
    """


def renderizar_logo(width: int = 180) -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown("### COPA")
        st.caption("Soluções Sustentáveis")


def renderizar_topo_portal() -> None:
    esquerda, direita = st.columns([4.5, 1.5], vertical_alignment="center")
    with esquerda:
        renderizar_logo(190)
    with direita:
        st.markdown(
            """
            <div style="text-align:right">
                <div class="sst-brand-tag">Copa Gestão</div>
                <div class="sst-brand-title">Portal interno SST</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:1px;background:#e5e7eb;margin:4px 0 24px'></div>", unsafe_allow_html=True)


def renderizar_portal_inicial() -> None:
    """Tela inicial do portal, usando componentes nativos para evitar HTML exibido como código."""
    st.markdown(
        f"""
        <div class="sst-portal-card">
            <div class="sst-hero-row">
                <div class="sst-hardhat">{_hardhat_svg()}</div>
                <div>
                    <div class="sst-kicker">Segurança, controle e rastreabilidade</div>
                    <div class="sst-hero-title">SST / EPI</div>
                    <div class="sst-hero-text">
                        Gestão integrada de colaboradores, EPIs, entregas, documentos e preparação
                        do fluxo de assinatura biométrica, com histórico e rastreabilidade.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Módulo", "SST / EPI")
    with col2:
        st.metric("Ambiente", "Desenvolvimento")
    with col3:
        st.metric("Rastreabilidade", "Ativa")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

def renderizar_cabecalho_modulo() -> None:
    """Cabeçalho interno robusto usando componentes nativos do Streamlit."""
    esquerda, direita = st.columns([5, 1.3], vertical_alignment="center")

    with esquerda:
        renderizar_logo(160)

    with direita:
        st.markdown(
            """
            <div style="text-align:right">
                <div class="sst-brand-tag">Copa Gestão</div>
                <div class="sst-brand-title">Segurança do Trabalho</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    col_icone, col_texto = st.columns([0.55, 7.45], vertical_alignment="center")

    with col_icone:
        st.markdown(
            f"""
            <div class="sst-hardhat" style="width:58px;height:58px;border-radius:15px">
                {_hardhat_svg()}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_texto:
        st.markdown(
            """
            <div class="sst-kicker">Gestão integrada de segurança</div>
            <div class="sst-hero-title" style="font-size:2.15rem;margin-bottom:5px">SST / EPI</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Colaboradores, controle de CA, entregas de EPI, documentos, ordens de serviço de SST "
            "e preparação para assinatura biométrica com rastreabilidade."
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

def mostrar_notificacao(mensagem: object) -> None:
    """Notificação temporária nativa do Streamlit."""
    if mensagem:
        st.toast(str(mensagem), icon="✅")


def renderizar_aviso_desenvolvimento() -> None:
    st.markdown(
        """
        <div class="sst-dev-note">
            🧪 <strong>AMBIENTE DE DESENVOLVIMENTO — MÓDULO SST/EPI</strong><br>
            <span style="font-size:.84rem;opacity:.8">
            Área destinada a testes. Não substitui o sistema oficial de manutenção.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_card_texto(titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="sst-section-note"><strong>{html.escape(titulo)}</strong><br>{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )
