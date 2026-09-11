from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select

from database import registrar_auditoria, transacao, utcnow
from sst_database import ASSINATURAS_SST, DOCUMENTOS_SST, inicializar_banco_sst
from sst_services import _storage_excluir

PRAZO_ASSINATURA_DIAS = 7


def limpar_documentos_sem_assinatura_expirados() -> dict:
    """Remove documentos pendentes há 7 dias sem apagar o histórico da entrega.

    A entrega de EPI continua preservada como fato operacional. Somente o documento
    eletrônico que ficou sem assinatura é removido da fila, dos indicadores e do
    armazenamento. Documentos com qualquer registro de assinatura são ignorados.
    """
    inicializar_banco_sst()
    limite = utcnow() - timedelta(days=PRAZO_ASSINATURA_DIAS)

    with transacao() as conn:
        candidatos = conn.execute(
            select(
                DOCUMENTOS_SST.c.id,
                DOCUMENTOS_SST.c.numero,
                DOCUMENTOS_SST.c.storage_path,
                DOCUMENTOS_SST.c.fechado_em,
            ).where(
                DOCUMENTOS_SST.c.status == "Aguardando Assinatura",
                DOCUMENTOS_SST.c.fechado_em.is_not(None),
                DOCUMENTOS_SST.c.fechado_em <= limite,
            )
        ).mappings().all()

        if not candidatos:
            return {"removidos": 0, "storage_falhas": 0}

        ids = [int(r["id"]) for r in candidatos]
        com_assinatura = set(
            conn.execute(
                select(ASSINATURAS_SST.c.documento_id).where(
                    ASSINATURAS_SST.c.documento_id.in_(ids)
                )
            ).scalars().all()
        )
        expirados = [r for r in candidatos if int(r["id"]) not in com_assinatura]

        for row in expirados:
            registrar_auditoria(
                conn,
                "sistema",
                "SST_DOCUMENTO_EXPIRADO_7_DIAS",
                "sst_documento",
                str(row["numero"]),
                "Documento aguardando assinatura por 7 dias; removido automaticamente da fila.",
            )

        if expirados:
            conn.execute(
                delete(DOCUMENTOS_SST).where(
                    DOCUMENTOS_SST.c.id.in_([int(r["id"]) for r in expirados])
                )
            )

    falhas = 0
    for row in expirados:
        caminho = row.get("storage_path")
        if not caminho:
            continue
        try:
            _storage_excluir(str(caminho))
        except Exception:
            # O registro já saiu do sistema; falha de limpeza do objeto não deve
            # restaurar um documento expirado nem interromper o uso do módulo.
            falhas += 1

    return {"removidos": len(expirados), "storage_falhas": falhas}
