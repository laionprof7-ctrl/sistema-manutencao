from __future__ import annotations

import os

from sqlalchemy import delete, insert, select, update

import database as db

RESET_KEY = "final_reset_20260911_v1"
_PROCESS_DONE = False


def _reset_ja_aplicado() -> bool:
    try:
        with db.ENGINE.connect() as conn:
            return conn.execute(
                select(db.CONTADORES.c.chave).where(db.CONTADORES.c.chave == RESET_KEY)
            ).first() is not None
    except Exception:
        return False


def aplicar_reset_final_uma_vez() -> dict[str, int | bool]:
    """Remove somente dados operacionais de teste, preservando usuários e estrutura.

    O marcador em ``contadores`` impede que um restart futuro apague dados reais.
    Dentro do mesmo processo, ``_PROCESS_DONE`` evita até a consulta do marcador
    nos reruns normais do Streamlit.
    """
    global _PROCESS_DONE
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("A limpeza final é proibida em produção.")
    if os.getenv("ALLOW_FINAL_RESET", "") != "CONFIRMAR_LIMPEZA_DE_TESTE":
        raise RuntimeError("Limpeza de teste não autorizada explicitamente.")
    if _PROCESS_DONE:
        return {"aplicado": False}

    if _reset_ja_aplicado():
        _PROCESS_DONE = True
        return {"aplicado": False}

    # Importa a pilha SST só na única execução em que o reset é necessário.
    from sst_database import (
        ASSINATURAS_SST,
        BIOMETRIAS_COLABORADORES,
        COLABORADORES,
        CONTADORES_SST,
        DOCUMENTOS_SST,
        ENTREGAS_EPI,
        EPIS,
        GHE,
        GHE_VINCULOS,
        ITENS_ENTREGA_EPI,
    )

    with db.ENGINE.connect() as conn:
        storage_paths = [
            str(path)
            for path in conn.execute(
                select(DOCUMENTOS_SST.c.storage_path).where(
                    DOCUMENTOS_SST.c.storage_path.is_not(None)
                )
            ).scalars().all()
            if path
        ]

    totais: dict[str, int | bool] = {"aplicado": True}

    with db.ENGINE.begin() as conn:
        # SST: respeita a ordem das chaves estrangeiras.
        totais["assinaturas"] = int(conn.execute(delete(ASSINATURAS_SST)).rowcount or 0)
        totais["biometrias"] = int(conn.execute(delete(BIOMETRIAS_COLABORADORES)).rowcount or 0)
        totais["documentos"] = int(conn.execute(delete(DOCUMENTOS_SST)).rowcount or 0)
        totais["itens_entrega"] = int(conn.execute(delete(ITENS_ENTREGA_EPI)).rowcount or 0)
        totais["entregas"] = int(conn.execute(delete(ENTREGAS_EPI)).rowcount or 0)
        totais["colaboradores"] = int(conn.execute(delete(COLABORADORES)).rowcount or 0)
        totais["ghe_vinculos"] = int(conn.execute(delete(GHE_VINCULOS)).rowcount or 0)
        totais["ghe"] = int(conn.execute(delete(GHE)).rowcount or 0)
        totais["epis"] = int(conn.execute(delete(EPIS)).rowcount or 0)
        conn.execute(delete(CONTADORES_SST))

        # Manutenção: remove OS/auditoria de teste, mas mantém contas de usuários.
        totais["ordens_servico"] = int(conn.execute(delete(db.CHAMADOS)).rowcount or 0)
        totais["auditoria"] = int(conn.execute(delete(db.AUDITORIA)).rowcount or 0)

        existe_os = conn.execute(
            select(db.CONTADORES.c.valor).where(db.CONTADORES.c.chave == "os")
        ).scalar_one_or_none()
        if existe_os is None:
            conn.execute(insert(db.CONTADORES).values(chave="os", valor=1000))
        else:
            conn.execute(
                update(db.CONTADORES)
                .where(db.CONTADORES.c.chave == "os")
                .values(valor=1000)
            )

        # Marcador gravado na mesma transação do reset. Depois disso, nenhum
        # restart/deploy repetirá a limpeza.
        conn.execute(insert(db.CONTADORES).values(chave=RESET_KEY, valor=1))

    # Storage é externo ao PostgreSQL. A remoção ocorre somente depois do commit.
    if storage_paths:
        try:
            from sst_services import _storage_excluir

            for path in storage_paths:
                _storage_excluir(path)
        except Exception:
            pass

    totais["pdfs_storage_solicitados"] = len(storage_paths)
    _PROCESS_DONE = True
    return totais
