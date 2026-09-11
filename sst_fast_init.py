from __future__ import annotations

from sqlalchemy import inspect, select, text

import sst_database as db

# A base já preparada não precisa repetir inspeções completas a cada novo processo
# do Streamlit. Esse número só deve mudar quando houver nova migração SST.
SCHEMA_VERSION = 2
SCHEMA_VERSION_KEY = "schema_sst_version"

_MIGRACOES = {
    "sst_colaboradores": [("ghe_id", "INTEGER")],
    "sst_epis": [("validade_ca", "DATE")],
    "sst_entregas_epi": [("motivo_entrega", "VARCHAR(80)")],
    "sst_itens_entrega_epi": [("validade_ca_no_momento", "DATE")],
    "sst_documentos": [
        ("entrega_id", "INTEGER"),
        ("pdf_arquivo", "BYTEA" if db.ENGINE.dialect.name == "postgresql" else "BLOB"),
        ("storage_path", "VARCHAR(500)"),
        ("nome_arquivo", "VARCHAR(255)"),
    ],
    "sst_assinaturas": [
        ("agente_id", "VARCHAR(120)"),
        ("dispositivo_modelo", "VARCHAR(120)"),
        ("dispositivo_serial", "VARCHAR(120)"),
        ("sdk_versao", "VARCHAR(80)"),
        ("evento_id", "VARCHAR(120)"),
        ("score_verificacao", "INTEGER"),
    ],
}

_INDICES = [
    db.IX_SST_EPI_ATIVO_VALIDADE,
    db.IX_SST_COLABORADOR_GHE,
    db.IX_SST_ENTREGA_MOTIVO,
    db.IX_SST_DOCUMENTO_ENTREGA,
    db.IX_SST_DOCUMENTO_STATUS_FECHADO,
    db.IX_SST_DOCUMENTO_TIPO_STATUS_CRIADO,
    db.IX_SST_ASSINATURA_EVENTO,
]


def _schema_ja_atualizado() -> bool:
    """Fast path: uma única consulta simples substitui dezenas de introspecções."""
    try:
        with db.ENGINE.connect() as conn:
            versao = conn.execute(
                select(db.CONTADORES_SST.c.valor).where(
                    db.CONTADORES_SST.c.chave == SCHEMA_VERSION_KEY
                )
            ).scalar_one_or_none()
        return int(versao or 0) >= SCHEMA_VERSION
    except Exception:
        # Base nova, tabela ausente ou versão antiga: segue para o caminho completo.
        return False


def _marcar_schema_atualizado() -> None:
    with db.ENGINE.begin() as conn:
        existente = conn.execute(
            select(db.CONTADORES_SST.c.valor).where(
                db.CONTADORES_SST.c.chave == SCHEMA_VERSION_KEY
            )
        ).scalar_one_or_none()
        if existente is None:
            conn.execute(
                db.CONTADORES_SST.insert().values(
                    chave=SCHEMA_VERSION_KEY,
                    valor=SCHEMA_VERSION,
                )
            )
        else:
            conn.execute(
                db.CONTADORES_SST.update()
                .where(db.CONTADORES_SST.c.chave == SCHEMA_VERSION_KEY)
                .values(valor=SCHEMA_VERSION)
            )


def inicializar_banco_sst_rapido() -> None:
    """Valida/migra a estrutura somente quando a versão do schema exigir."""
    if _schema_ja_atualizado():
        return

    insp = inspect(db.ENGINE)
    tabelas_existentes = set(insp.get_table_names())
    tabelas_necessarias = {t.name for t in db.TABELAS_SST}

    if not tabelas_necessarias.issubset(tabelas_existentes):
        db.METADATA.create_all(db.ENGINE, tables=db.TABELAS_SST)
        insp = inspect(db.ENGINE)

    alteracoes: list[tuple[str, str, str]] = []
    for tabela, migracoes in _MIGRACOES.items():
        existentes = {c["name"] for c in insp.get_columns(tabela)}
        for coluna, ddl in migracoes:
            if coluna not in existentes:
                alteracoes.append((tabela, coluna, ddl))

    if alteracoes:
        with db.ENGINE.begin() as conn:
            for tabela, coluna, ddl in alteracoes:
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl}"))

    indices_por_tabela: dict[str, set[str]] = {}
    for indice in _INDICES:
        tabela = indice.table.name
        if tabela not in indices_por_tabela:
            indices_por_tabela[tabela] = {
                item["name"] for item in insp.get_indexes(tabela) if item.get("name")
            }
        if indice.name not in indices_por_tabela[tabela]:
            indice.create(bind=db.ENGINE, checkfirst=False)
            indices_por_tabela[tabela].add(indice.name)

    db._inicializar_contador_documentos_ano_atual()
    _marcar_schema_atualizado()
