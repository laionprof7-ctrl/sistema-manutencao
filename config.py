import os
from datetime import timedelta, timezone

FUSO_BR = timezone(timedelta(hours=-3))
ARQUIVO_LOGO = "logo.png"
ARQUIVO_PAPEL_TIMBRADO = "8. Papel Timbrado.docx"

VEICULOS = [
    "Caminhão Compactador", "Caminhão Poliguindaste", "Caminhão Roll-On",
    "Caminhão Pipa", "Caminhão Basculante", "Carregadeira",
    "Retroescavadeira", "Trator de Esteira", "Motoniveladora",
    "Pick-up Operacional", "Van de Equipe", "Veículo Leve / Apoio"
]

NIVEIS = {
    1.0: "Motorista",
    2.0: "Operacional",
    3.0: "Coordenador",
    3.5: "Coordenador Plus",
    4.0: "Administrador Global",
}
STATUS_VALIDOS = ["Aguardando Aprovação", "Aguardando Manutenção", "Em Andamento", "Concluído"]
PRIORIDADES = ["Alta", "Média", "Baixa"]

def _setting(nome: str, padrao: str) -> str:
    valor = os.getenv(nome)
    if valor not in (None, ""):
        return str(valor)
    try:
        import streamlit as st
        if nome in st.secrets:
            return str(st.secrets[nome])
    except Exception:
        pass
    return padrao


APP_ENV = _setting("APP_ENV", "development").strip().lower()
SESSION_IDLE_MINUTES = int(_setting("SESSION_IDLE_MINUTES", "60"))


def get_database_url() -> str:
    url = _setting("DATABASE_URL", "").strip()

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    if not url:
        if APP_ENV == "production":
            raise RuntimeError("DATABASE_URL é obrigatória em produção.")
        return "sqlite:///copa_manutencao_dev.db"

    if APP_ENV == "production" and not url.startswith("postgresql+"):
        raise RuntimeError("Em produção, use PostgreSQL em DATABASE_URL.")
    return url
