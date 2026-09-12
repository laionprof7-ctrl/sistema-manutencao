from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer,
    MetaData, String, Table, Text, create_engine, insert,
    select, update
)
from sqlalchemy.engine import Engine
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from config import get_database_url

DATABASE_URL = get_database_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
ENGINE: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
    connect_args=_connect_args,
)
METADATA = MetaData()

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(ENGINE, "connect")
    def _sqlite_fk_on(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

USUARIOS = Table(
    "usuarios", METADATA,
    Column("usuario", String(40), primary_key=True),
    Column("senha", Text, nullable=False),
    Column("nome", String(160), nullable=False),
    Column("nivel", Float, nullable=False),
    Column("ativo", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
    CheckConstraint("nivel IN (1.0, 2.0, 3.0, 3.5, 4.0)", name="ck_usuario_nivel"),
)

CHAMADOS = Table(
    "chamados", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_os", String(32), unique=True, nullable=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("solicitante_usuario", String(40), ForeignKey("usuarios.usuario", ondelete="RESTRICT"), nullable=True),
    Column("motorista", String(160), nullable=False),
    Column("veiculo", String(160), nullable=False),
    Column("placa", String(60), nullable=False),
    Column("descricao_problema", Text, nullable=False),
    Column("status", String(60), nullable=False),
    Column("prioridade", String(20), nullable=False),
    Column("aprovado_coordenador", Boolean, nullable=False, default=False),
    Column("aprovado_por", String(40), ForeignKey("usuarios.usuario", ondelete="SET NULL"), nullable=True),
    Column("data_aprovacao", DateTime(timezone=True), nullable=True),
    Column("mecanico_responsavel", String(160), nullable=True),
    Column("data_liberacao", DateTime(timezone=True), nullable=True),
    Column("arquivado", Boolean, nullable=False, default=False),
    Column("excluido", Boolean, nullable=False, default=False),
    Column("excluido_em", DateTime(timezone=True), nullable=True),
    Column("excluido_por", String(40), ForeignKey("usuarios.usuario", ondelete="SET NULL"), nullable=True),
    Column("versao", Integer, nullable=False, default=1),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
    CheckConstraint("status IN ('Aguardando Aprovação','Aguardando Manutenção','Em Andamento','Concluído')", name="ck_chamado_status"),
    CheckConstraint("prioridade IN ('Pendente','Alta','Média','Baixa')", name="ck_chamado_prioridade"),
    sqlite_autoincrement=True,
)
Index("ix_chamados_placa", CHAMADOS.c.placa)
Index("ix_chamados_status", CHAMADOS.c.status)
Index("ix_chamados_criado_em", CHAMADOS.c.criado_em)

AUDITORIA = Table(
    "auditoria", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("ator", String(40), nullable=False),
    Column("acao", String(80), nullable=False),
    Column("entidade", String(40), nullable=False),
    Column("entidade_id", String(80), nullable=True),
    Column("detalhes", Text, nullable=True),
)
Index("ix_auditoria_criado_em", AUDITORIA.c.criado_em)
Index("ix_auditoria_ator", AUDITORIA.c.ator)

CONTADORES = Table(
    "contadores", METADATA,
    Column("chave", String(40), primary_key=True),
    Column("valor", Integer, nullable=False),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def agora_brasil() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Bahia")).strftime("%d/%m/%Y %H:%M")


@contextmanager
def transacao():
    with ENGINE.begin() as conn:
        yield conn


def inicializar_banco() -> None:
    METADATA.create_all(ENGINE)
    try:
        with ENGINE.begin() as conn:
            existe = conn.execute(select(CONTADORES.c.chave).where(CONTADORES.c.chave == "os")).first()
            if not existe:
                conn.execute(insert(CONTADORES).values(chave="os", valor=1000))
    except IntegrityError:
        pass


def healthcheck() -> bool:
    try:
        with ENGINE.connect() as conn:
            conn.execute(select(1))
        return True
    except Exception:
        return False


def obter_usuario(usuario: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        row = conn.execute(select(USUARIOS).where(USUARIOS.c.usuario == usuario)).mappings().first()
    return dict(row) if row else None


def listar_usuarios() -> pd.DataFrame:
    with ENGINE.connect() as conn:
        return pd.read_sql(select(USUARIOS).order_by(USUARIOS.c.nome), conn)


def arquivar_chamados_expirados() -> int:
    """Arquiva automaticamente OS não aprovadas há mais de 7 dias, preservando o histórico."""
    limite = utcnow() - timedelta(days=7)
    with ENGINE.begin() as conn:
        expirados = conn.execute(
            select(CHAMADOS.c.id, CHAMADOS.c.id_os).where(
                (CHAMADOS.c.aprovado_coordenador == False)
                & (CHAMADOS.c.arquivado == False)
                & (CHAMADOS.c.excluido == False)
                & (CHAMADOS.c.criado_em < limite)
            )
        ).mappings().all()
        if not expirados:
            return 0
        arquivados = []
        for row in expirados:
            result = conn.execute(
                update(CHAMADOS)
                .where(
                    (CHAMADOS.c.id == row["id"])
                    & (CHAMADOS.c.aprovado_coordenador == False)
                    & (CHAMADOS.c.arquivado == False)
                    & (CHAMADOS.c.excluido == False)
                    & (CHAMADOS.c.criado_em < limite)
                )
                .values(arquivado=True, atualizado_em=utcnow(), versao=CHAMADOS.c.versao + 1)
            )
            if result.rowcount == 1:
                arquivados.append(row)
                registrar_auditoria(
                    conn, "sistema", "OS_ARQUIVADA_EXPIRACAO", "chamado", row["id_os"],
                    "Chamado não aprovado no prazo de 7 dias."
                )
        return len(arquivados)


def listar_chamados() -> pd.DataFrame:
    arquivar_chamados_expirados()
    stmt = select(
        CHAMADOS.c.id,
        CHAMADOS.c.id_os.label("ID_OS"),
        CHAMADOS.c.criado_em.label("Data_dt"),
        CHAMADOS.c.motorista.label("Motorista"),
        CHAMADOS.c.veiculo.label("Veiculo"),
        CHAMADOS.c.placa.label("Placa"),
        CHAMADOS.c.descricao_problema.label("Descricao_Problema"),
        CHAMADOS.c.status.label("Status"),
        CHAMADOS.c.prioridade.label("Prioridade"),
        CHAMADOS.c.aprovado_coordenador.label("Aprovado_bool"),
        CHAMADOS.c.data_aprovacao.label("Data_Aprovacao_dt"),
        CHAMADOS.c.mecanico_responsavel.label("Mecanico_Responsavel"),
        CHAMADOS.c.data_liberacao.label("Data_Liberacao_dt"),
        CHAMADOS.c.arquivado.label("Arquivado_bool"),
        CHAMADOS.c.excluido.label("Excluido_bool"),
        CHAMADOS.c.versao.label("Versao"),
    ).where(CHAMADOS.c.excluido == False).order_by(CHAMADOS.c.id.desc())
    with ENGINE.connect() as conn:
        df = pd.read_sql(stmt, conn)
    if df.empty:
        for col in ["Data", "Data_Aprovacao", "Data_Liberacao", "Aprovado_Coordenador", "Arquivado"]:
            df[col] = []
        return df
    def fmt(v):
        if pd.isna(v):
            return ""
        ts = pd.Timestamp(v)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert("America/Bahia").strftime("%d/%m/%Y %H:%M")
    df["Data"] = df["Data_dt"].apply(fmt)
    df["Data_Aprovacao"] = df["Data_Aprovacao_dt"].apply(fmt)
    df["Data_Liberacao"] = df["Data_Liberacao_dt"].apply(fmt)
    df["Aprovado_Coordenador"] = df["Aprovado_bool"].map({True: "Sim", False: "Não"})
    df["Arquivado"] = df["Arquivado_bool"].map({True: "Sim", False: "Não"})
    return df


def resumo_chamados() -> dict[str, int]:
    """Contadores do dashboard; concluídos considera somente os últimos 7 dias."""
    from sqlalchemy import case, func

    arquivar_chamados_expirados()
    limite_concluidos = utcnow() - timedelta(days=7)
    stmt = select(
        func.count(case((CHAMADOS.c.status == "Aguardando Aprovação", 1))).label("pendentes"),
        func.count(case((CHAMADOS.c.status == "Em Andamento", 1))).label("andamento"),
        func.count(case((
            (CHAMADOS.c.status == "Concluído")
            & (CHAMADOS.c.data_liberacao.is_not(None))
            & (CHAMADOS.c.data_liberacao >= limite_concluidos),
            1
        ))).label("concluidos"),
    ).where(
        (CHAMADOS.c.excluido == False) & (CHAMADOS.c.arquivado == False)
    )
    with ENGINE.connect() as conn:
        row = conn.execute(stmt).mappings().one()
    return {k: int(row[k] or 0) for k in ("pendentes", "andamento", "concluidos")}


def registrar_auditoria(conn, ator: str, acao: str, entidade: str, entidade_id: str | None = None, detalhes: str | None = None) -> None:
    conn.execute(insert(AUDITORIA).values(
        criado_em=utcnow(), ator=ator, acao=acao, entidade=entidade,
        entidade_id=entidade_id, detalhes=(detalhes or "")[:4000]
    ))


def listar_auditoria(limite: int = 200) -> pd.DataFrame:
    stmt = select(AUDITORIA).order_by(AUDITORIA.c.id.desc()).limit(max(1, min(limite, 1000)))
    with ENGINE.connect() as conn:
        return pd.read_sql(stmt, conn)
