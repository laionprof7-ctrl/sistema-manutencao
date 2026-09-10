from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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
    select,
    text,
)

from database import ENGINE, METADATA, transacao


GHE = Table(
    "sst_ghe",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("codigo", String(40), nullable=False, unique=True),
    Column("nome", String(160), nullable=False),
    Column("riscos", Text, nullable=True),
    Column("medidas_preventivas", Text, nullable=True),
    Column("epis_recomendados", Text, nullable=True),
    Column("orientacoes", Text, nullable=True),
    Column("ativo", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
)
Index("ix_sst_ghe_nome", GHE.c.nome)
Index("ix_sst_ghe_ativo", GHE.c.ativo)


GHE_VINCULOS = Table(
    "sst_ghe_vinculos",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ghe_id", Integer, ForeignKey("sst_ghe.id", ondelete="CASCADE"), nullable=False),
    Column("setor", String(160), nullable=False),
    Column("funcao", String(160), nullable=False),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    UniqueConstraint("ghe_id", "setor", "funcao", name="uq_sst_ghe_vinculo"),
)
Index("ix_sst_ghe_vinculo_ghe", GHE_VINCULOS.c.ghe_id)
Index("ix_sst_ghe_vinculo_setor_funcao", GHE_VINCULOS.c.setor, GHE_VINCULOS.c.funcao)


COLABORADORES = Table(
    "sst_colaboradores",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("matricula", String(40), nullable=True),
    Column("nome", String(160), nullable=False),
    Column("cpf", String(14), nullable=True),
    Column("funcao", String(160), nullable=False),
    Column("setor", String(160), nullable=True),
    Column("ghe_id", Integer, ForeignKey("sst_ghe.id", ondelete="SET NULL"), nullable=True),
    Column("data_admissao", Date, nullable=True),
    Column("ativo", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
    UniqueConstraint("matricula", name="uq_sst_colaborador_matricula"),
    UniqueConstraint("cpf", name="uq_sst_colaborador_cpf"),
)
Index("ix_sst_colaborador_nome", COLABORADORES.c.nome)
Index("ix_sst_colaborador_ativo", COLABORADORES.c.ativo)
IX_SST_COLABORADOR_GHE = Index("ix_sst_colaborador_ghe", COLABORADORES.c.ghe_id)


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
    Column("motivo_entrega", String(80), nullable=True),
    Column("observacao", Text, nullable=True),  # legado: preservado para compatibilidade/histórico
    Column("status", String(30), nullable=False, default="Registrada"),
    Column("criado_em", DateTime(timezone=True), nullable=False),
)
Index("ix_sst_entrega_colaborador", ENTREGAS_EPI.c.colaborador_id)
Index("ix_sst_entrega_data", ENTREGAS_EPI.c.entregue_em)
IX_SST_ENTREGA_MOTIVO = Index("ix_sst_entrega_motivo", ENTREGAS_EPI.c.motivo_entrega)


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
    Column("entrega_id", Integer, ForeignKey("sst_entregas_epi.id", ondelete="SET NULL"), nullable=True),
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
IX_SST_DOCUMENTO_ENTREGA = Index("ix_sst_documento_entrega", DOCUMENTOS_SST.c.entrega_id)
Index("ix_sst_documento_tipo", DOCUMENTOS_SST.c.tipo)
Index("ix_sst_documento_status", DOCUMENTOS_SST.c.status)
IX_SST_DOCUMENTO_STATUS_FECHADO = Index("ix_sst_documento_status_fechado", DOCUMENTOS_SST.c.status, DOCUMENTOS_SST.c.fechado_em)
IX_SST_DOCUMENTO_TIPO_STATUS_CRIADO = Index(
    "ix_sst_documento_tipo_status_criado", DOCUMENTOS_SST.c.tipo, DOCUMENTOS_SST.c.status, DOCUMENTOS_SST.c.criado_em
)


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


CONTADORES_SST = Table(
    "sst_contadores",
    METADATA,
    Column("chave", String(80), primary_key=True),
    Column("valor", Integer, nullable=False, default=0),
)


TABELAS_SST = [
    GHE,
    GHE_VINCULOS,
    COLABORADORES,
    EPIS,
    ENTREGAS_EPI,
    ITENS_ENTREGA_EPI,
    DOCUMENTOS_SST,
    ASSINATURAS_SST,
    CONTADORES_SST,
]


def _adicionar_coluna_se_ausente(tabela: str, coluna: str, ddl: str) -> None:
    insp = inspect(ENGINE)
    existentes = {c["name"] for c in insp.get_columns(tabela)}
    if coluna not in existentes:
        with ENGINE.begin() as conn:
            conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl}"))


def _inicializar_contador_documentos_ano_atual() -> None:
    ano = datetime.now(ZoneInfo("America/Bahia")).year
    chave = f"documentos_{ano}"
    prefixo = f"SST-{ano}-"
    with transacao() as conn:
        existente = conn.execute(select(CONTADORES_SST.c.valor).where(CONTADORES_SST.c.chave == chave)).scalar_one_or_none()
        if existente is not None:
            return
        numeros = conn.execute(
            select(DOCUMENTOS_SST.c.numero).where(DOCUMENTOS_SST.c.numero.like(f"{prefixo}%"))
        ).scalars().all()
        maior = 0
        for numero in numeros:
            try:
                maior = max(maior, int(str(numero).split("-")[-1]))
            except (TypeError, ValueError):
                continue
        if ENGINE.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
            stmt = dialect_insert(CONTADORES_SST).values(chave=chave, valor=maior).on_conflict_do_nothing(index_elements=[CONTADORES_SST.c.chave])
        elif ENGINE.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
            stmt = dialect_insert(CONTADORES_SST).values(chave=chave, valor=maior).on_conflict_do_nothing(index_elements=[CONTADORES_SST.c.chave])
        else:
            stmt = CONTADORES_SST.insert().values(chave=chave, valor=maior)
        conn.execute(stmt)


def inicializar_banco_sst() -> None:
    """Cria tabelas SST e aplica migrações aditivas sem apagar dados existentes."""
    METADATA.create_all(ENGINE, tables=TABELAS_SST)

    _adicionar_coluna_se_ausente("sst_colaboradores", "ghe_id", "INTEGER")
    _adicionar_coluna_se_ausente("sst_epis", "validade_ca", "DATE")
    _adicionar_coluna_se_ausente("sst_entregas_epi", "motivo_entrega", "VARCHAR(80)")
    _adicionar_coluna_se_ausente("sst_itens_entrega_epi", "validade_ca_no_momento", "DATE")
    _adicionar_coluna_se_ausente("sst_documentos", "entrega_id", "INTEGER")

    binario = "BYTEA" if ENGINE.dialect.name == "postgresql" else "BLOB"
    _adicionar_coluna_se_ausente("sst_documentos", "pdf_arquivo", binario)
    _adicionar_coluna_se_ausente("sst_documentos", "nome_arquivo", "VARCHAR(255)")

    IX_SST_EPI_ATIVO_VALIDADE.create(bind=ENGINE, checkfirst=True)
    IX_SST_COLABORADOR_GHE.create(bind=ENGINE, checkfirst=True)
    IX_SST_ENTREGA_MOTIVO.create(bind=ENGINE, checkfirst=True)
    IX_SST_DOCUMENTO_ENTREGA.create(bind=ENGINE, checkfirst=True)
    IX_SST_DOCUMENTO_STATUS_FECHADO.create(bind=ENGINE, checkfirst=True)
    IX_SST_DOCUMENTO_TIPO_STATUS_CRIADO.create(bind=ENGINE, checkfirst=True)

    _inicializar_contador_documentos_ano_atual()
