from __future__ import annotations

from sqlalchemy import inspect, text

import sst_database as db


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


def inicializar_banco_sst_rapido() -> None:
    """Inicialização compatível, reduzindo consultas repetidas de metadados.

    Em uma base já criada, evita repetir create_all/checkfirst para cada objeto e
    lê as colunas uma única vez por tabela. Em uma base nova, mantém o caminho
    seguro usando create_all antes das migrações aditivas.
    """
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

    # Os índices abaixo já existem no ambiente normal. Só fazemos a criação
    # quando o inspector mostra que algum está ausente.
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
