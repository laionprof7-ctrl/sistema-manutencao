from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    inspect,
    text,
)

from database import ENGINE, METADATA


COLABORADORES = Table(
    "sst_colaboradores",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("matricula", String(40), nullable=True),
    Column("nome", String(160), nullable=False),
    Column("cpf", String(14), nullable=True),
    Column("funcao", String(160), nullable=False),
    Column("setor", String(160), nullable=True),
    Column("data_admissao", Date, nullable=True),
    Column("ativo", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
    UniqueConstraint("matricula", name="uq_sst_colaborador_matricula"),
    UniqueConstraint("cpf", name="uq_sst_colaborador_cpf"),
)
Index("ix_sst_colaborador_nome", COLABORADORES.c.nome)
Index("ix_sst_colaborador_ativo", COLABORADORES.c.ativo)


EPIS = Table(
    "sst_epis",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nome", String(180), nullable=False),
    Column("ca", String(40), nullable=False),
    Column("fabricante", String(160), nullable=True),
    Column("validade_ca", Date, nullable=True),
    Column("unidade", String(40), nullable=False, default="unidade"),
    Column("ativo", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
    UniqueConstraint("nome", "ca", name="uq_sst_epi_nome_ca"),
)
Index("ix_sst_epi_nome", EPIS.c.nome)
Index("ix_sst_epi_ativo", EPIS.c.ativo)
Index("ix_sst_epi_validade_ca", EPIS.c.validade_ca)
IX_SST_EPI_ATIVO_VALIDADE = Index("ix_sst_epi_ativo_validade", EPIS.c.ativo, EPIS.c.validade_ca)


ENTREGAS_EPI = Table(
    "sst_entregas_epi",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("colaborador_id", Integer, ForeignKey("sst_colaboradores.id", ondelete="RESTRICT"), nullable=False),
    Column("responsavel_usuario", String(40), ForeignKey("usuarios.usuario", ondelete="SET NULL"), nullable=True),
    Column("entregue_em", DateTime(timezone=True), nullable=False),
    Column("observacao", Text, nullable=True),
    Column("status", String(30), nullable=False, default="Registrada"),
    Column("criado_em", DateTime(timezone=True), nullable=False),
)
Index("ix_sst_entrega_colaborador", ENTREGAS_EPI.c.colaborador_id)
Index("ix_sst_entrega_data", ENTREGAS_EPI.c.entregue_em)


ITENS_ENTREGA_EPI = Table(
    "sst_itens_entrega_epi",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("entrega_id", Integer, ForeignKey("sst_entregas_epi.id", ondelete="CASCADE"), nullable=False),
    Column("epi_id", Integer, ForeignKey("sst_epis.id", ondelete="RESTRICT"), nullable=False),
    Column("quantidade", Integer, nullable=False, default=1),
    Column("ca_no_momento", String(40), nullable=True),
    Column("validade_ca_no_momento", Date, nullable=True),
)
Index("ix_sst_item_entrega", ITENS_ENTREGA_EPI.c.entrega_id)


DOCUMENTOS_SST = Table(
    "sst_documentos",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("numero", String(50), nullable=False, unique=True),
    Column("colaborador_id", Integer, ForeignKey("sst_colaboradores.id", ondelete="RESTRICT"), nullable=False),
    Column("tipo", String(80), nullable=False),
    Column("motivo", String(80), nullable=True),
    Column("titulo", String(220), nullable=False),
    Column("conteudo_snapshot", Text, nullable=True),
    Column("hash_documento", String(64), nullable=True),
    Column("pdf_arquivo", LargeBinary, nullable=True),
    Column("nome_arquivo", String(255), nullable=True),
    Column("status", String(30), nullable=False, default="Rascunho"),
    Column("criado_por", String(40), ForeignKey("usuarios.usuario", ondelete="SET NULL"), nullable=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("fechado_em", DateTime(timezone=True), nullable=True),
)
Index("ix_sst_documento_colaborador", DOCUMENTOS_SST.c.colaborador_id)
Index("ix_sst_documento_tipo", DOCUMENTOS_SST.c.tipo)
Index("ix_sst_documento_status", DOCUMENTOS_SST.c.status)
IX_SST_DOCUMENTO_STATUS_FECHADO = Index("ix_sst_documento_status_fechado", DOCUMENTOS_SST.c.status, DOCUMENTOS_SST.c.fechado_em)


ASSINATURAS_SST = Table(
    "sst_assinaturas",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("documento_id", Integer, ForeignKey("sst_documentos.id", ondelete="RESTRICT"), nullable=False),
    Column("colaborador_id", Integer, ForeignKey("sst_colaboradores.id", ondelete="RESTRICT"), nullable=False),
    Column("metodo", String(40), nullable=False, default="Biometria"),
    Column("status", String(30), nullable=False),
    Column("hash_documento", String(64), nullable=False),
    Column("assinado_em", DateTime(timezone=True), nullable=False),
    Column("estacao", String(160), nullable=True),
    Column("referencia_biometrica", String(255), nullable=True),
    Column("detalhes", Text, nullable=True),
)
Index("ix_sst_assinatura_documento", ASSINATURAS_SST.c.documento_id)
Index("ix_sst_assinatura_colaborador", ASSINATURAS_SST.c.colaborador_id)
Index("ix_sst_assinatura_data", ASSINATURAS_SST.c.assinado_em)


TABELAS_SST = [
    COLABORADORES,
    EPIS,
    ENTREGAS_EPI,
    ITENS_ENTREGA_EPI,
    DOCUMENTOS_SST,
    ASSINATURAS_SST,
]


def _adicionar_coluna_se_ausente(tabela: str, coluna: str, ddl: str) -> None:
    insp = inspect(ENGINE)
    existentes = {c["name"] for c in insp.get_columns(tabela)}
    if coluna not in existentes:
        with ENGINE.begin() as conn:
            conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl}"))


def inicializar_banco_sst() -> None:
    """Cria tabelas SST e aplica migrações aditivas, sem apagar dados existentes."""
    METADATA.create_all(ENGINE, tables=TABELAS_SST)

    _adicionar_coluna_se_ausente("sst_epis", "validade_ca", "DATE")
    _adicionar_coluna_se_ausente("sst_itens_entrega_epi", "validade_ca_no_momento", "DATE")

    # PostgreSQL usa BYTEA; SQLite usa BLOB.
    binario = "BYTEA" if ENGINE.dialect.name == "postgresql" else "BLOB"
    _adicionar_coluna_se_ausente("sst_documentos", "pdf_arquivo", binario)
    _adicionar_coluna_se_ausente("sst_documentos", "nome_arquivo", "VARCHAR(255)")

    # create_all não adiciona índices novos em tabelas já existentes; criamos com checkfirst.
    IX_SST_EPI_ATIVO_VALIDADE.create(bind=ENGINE, checkfirst=True)
    IX_SST_DOCUMENTO_STATUS_FECHADO.create(bind=ENGINE, checkfirst=True)
