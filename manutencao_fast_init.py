from __future__ import annotations

import threading
import time

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

import database as db

SCHEMA_MARKER = "schema_manutencao_v1"
ARQUIVAMENTO_INTERVALO_SEGUNDOS = 300

_lock = threading.Lock()
_ultimo_arquivamento = 0.0
_arquivar_original = db.arquivar_chamados_expirados


def inicializar_banco_rapido() -> None:
    """Evita create_all/metadados em toda nova instância quando o schema já está pronto."""
    try:
        with db.ENGINE.connect() as conn:
            pronto = conn.execute(
                select(db.CONTADORES.c.chave).where(db.CONTADORES.c.chave == SCHEMA_MARKER)
            ).first()
        if pronto:
            return
    except Exception:
        # Banco novo/legado: cai no caminho completo abaixo.
        pass

    db.METADATA.create_all(db.ENGINE)
    try:
        with db.ENGINE.begin() as conn:
            if not conn.execute(
                select(db.CONTADORES.c.chave).where(db.CONTADORES.c.chave == "os")
            ).first():
                conn.execute(insert(db.CONTADORES).values(chave="os", valor=1000))

            if not conn.execute(
                select(db.CONTADORES.c.chave).where(db.CONTADORES.c.chave == SCHEMA_MARKER)
            ).first():
                conn.execute(insert(db.CONTADORES).values(chave=SCHEMA_MARKER, valor=1))
    except IntegrityError:
        pass


def arquivar_chamados_expirados_rapido() -> int:
    """Executa a limpeza de OS expiradas no máximo uma vez a cada 5 minutos por processo."""
    global _ultimo_arquivamento
    agora = time.monotonic()
    if agora - _ultimo_arquivamento < ARQUIVAMENTO_INTERVALO_SEGUNDOS:
        return 0

    with _lock:
        agora = time.monotonic()
        if agora - _ultimo_arquivamento < ARQUIVAMENTO_INTERVALO_SEGUNDOS:
            return 0
        removidos = _arquivar_original()
        _ultimo_arquivamento = time.monotonic()
        return removidos
