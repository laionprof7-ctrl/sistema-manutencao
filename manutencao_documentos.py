from __future__ import annotations

import hashlib
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
from sqlalchemy import func, insert, select, update

from database import DOCUMENTOS_MANUTENCAO, ENGINE, transacao, utcnow
from reports import gerar_relatorio_pdf

STORAGE_BUCKET_MANUTENCAO = "documentos-manutencao"
STORAGE_LIMITE_BYTES = 10 * 1024 * 1024


class DocumentoManutencaoError(RuntimeError):
    pass


def _segredo(nome: str) -> str:
    valor = os.getenv(nome)
    if valor:
        return valor.strip()
    try:
        import streamlit as st
        valor = st.secrets.get(nome)
        if valor:
            return str(valor).strip()
    except Exception:
        pass
    raise DocumentoManutencaoError(f"Configuração {nome} não encontrada.")


def _storage_config() -> tuple[str, str]:
    url = _segredo("SUPABASE_URL").rstrip("/")
    chave = _segredo("SUPABASE_SERVICE_ROLE_KEY")
    if not url.startswith("https://"):
        raise DocumentoManutencaoError("Configuração do Storage inválida.")
    return url, chave


def _storage_requisicao(metodo: str, path: str, dados: bytes | None = None) -> bytes:
    url_base, chave = _storage_config()
    caminho = quote(path, safe="/")
    url = f"{url_base}/storage/v1/object/{STORAGE_BUCKET_MANUTENCAO}/{caminho}"
    headers = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "User-Agent": "Copa-Manutencao-Backend/1.0",
    }
    if dados is not None:
        headers["Content-Type"] = "application/pdf"
        headers["x-upsert"] = "false"
    try:
        with urlopen(Request(url, data=dados, headers=headers, method=metodo), timeout=30) as resposta:
            return resposta.read()
    except (HTTPError, URLError) as exc:
        raise DocumentoManutencaoError("Não foi possível acessar o Storage de documentos.") from exc


def _storage_enviar(path: str, pdf: bytes, hash_documento: str) -> None:
    try:
        _storage_requisicao("POST", path, pdf)
        return
    except DocumentoManutencaoError:
        # Uma tentativa anterior pode ter enviado o arquivo e falhado antes de
        # registrar o caminho no banco. Nesse caso aceitamos apenas o mesmo PDF.
        try:
            existente = _storage_requisicao("GET", path)
        except DocumentoManutencaoError:
            raise
        if hashlib.sha256(existente).hexdigest() != hash_documento:
            raise DocumentoManutencaoError("Já existe outro documento no caminho reservado.")


def _fmt_data(valor) -> str:
    if not valor:
        return ""
    data = pd.Timestamp(valor)
    if data.tzinfo is None:
        data = data.tz_localize("UTC")
    return data.tz_convert("America/Bahia").strftime("%d/%m/%Y %H:%M")


def _gerar_pdf(row: dict, versao_documento: int) -> tuple[bytes, str]:
    dados = pd.DataFrame([{
        "ID_OS": row["id_os"],
        "Data": _fmt_data(row["criado_em"]),
        "Motorista": row["motorista"],
        "Veiculo": row["veiculo"],
        "Placa": row["placa"],
        "Descricao_Problema": row["descricao_problema"],
        "Status": row["status"],
        "Prioridade": row["prioridade"],
        "Data_Aprovacao": _fmt_data(row["data_aprovacao"]),
        "Mecanico_Responsavel": row["mecanico_responsavel"],
        "Data_Liberacao": _fmt_data(row["data_liberacao"]),
    }])
    pdf = gerar_relatorio_pdf(
        dados,
        f"Documento final · {row['id_os']} · Versão {versao_documento}",
    )
    if not pdf or len(pdf) > STORAGE_LIMITE_BYTES:
        raise DocumentoManutencaoError("O PDF final excede o limite permitido.")
    id_seguro = re.sub(r"[^A-Za-z0-9_-]+", "_", str(row["id_os"])).strip("_")
    nome = f"Relatorio_{id_seguro}_v{versao_documento}.pdf"
    return pdf, nome


def registrar_documento_final(conn, chamado: dict, gerado_por: str) -> int:
    """Registra uma versão imutável do PDF dentro da transação de conclusão."""
    ultima = conn.execute(
        select(func.max(DOCUMENTOS_MANUTENCAO.c.versao_documento)).where(
            DOCUMENTOS_MANUTENCAO.c.chamado_id == int(chamado["id"])
        )
    ).scalar_one_or_none()
    versao_documento = int(ultima or 0) + 1
    pdf, nome = _gerar_pdf(chamado, versao_documento)
    hash_documento = hashlib.sha256(pdf).hexdigest()
    resultado = conn.execute(insert(DOCUMENTOS_MANUTENCAO).values(
        chamado_id=int(chamado["id"]),
        id_os=chamado["id_os"],
        versao_documento=versao_documento,
        hash_documento=hash_documento,
        pdf_arquivo=pdf,
        storage_path=None,
        nome_arquivo=nome,
        gerado_por=gerado_por,
        gerado_em=utcnow(),
    ))
    return int(resultado.inserted_primary_key[0])


def sincronizar_documento(documento_id: int) -> bool:
    """Move o PDF preservado no banco para o Storage; falha mantém a cópia local."""
    if ENGINE.dialect.name != "postgresql":
        return True
    with transacao() as conn:
        row = conn.execute(
            select(DOCUMENTOS_MANUTENCAO).where(DOCUMENTOS_MANUTENCAO.c.id == int(documento_id))
        ).mappings().first()
    if not row or row.get("storage_path"):
        return bool(row)
    if not row.get("pdf_arquivo"):
        return False
    ano = pd.Timestamp(row["gerado_em"]).year
    path = f"{ano}/{row['id_os']}/{row['nome_arquivo']}"
    pdf = bytes(row["pdf_arquivo"])
    try:
        _storage_enviar(path, pdf, row["hash_documento"])
    except DocumentoManutencaoError:
        return False
    with transacao() as conn:
        conn.execute(
            update(DOCUMENTOS_MANUTENCAO)
            .where(
                (DOCUMENTOS_MANUTENCAO.c.id == int(documento_id))
                & (DOCUMENTOS_MANUTENCAO.c.storage_path.is_(None))
            )
            .values(storage_path=path, pdf_arquivo=None)
        )
    return True


def listar_documentos_os(chamado_id: int) -> list[dict]:
    with transacao() as conn:
        rows = conn.execute(
            select(
                DOCUMENTOS_MANUTENCAO.c.id,
                DOCUMENTOS_MANUTENCAO.c.versao_documento,
                DOCUMENTOS_MANUTENCAO.c.nome_arquivo,
                DOCUMENTOS_MANUTENCAO.c.hash_documento,
                DOCUMENTOS_MANUTENCAO.c.gerado_por,
                DOCUMENTOS_MANUTENCAO.c.gerado_em,
            )
            .where(DOCUMENTOS_MANUTENCAO.c.chamado_id == int(chamado_id))
            .order_by(DOCUMENTOS_MANUTENCAO.c.versao_documento.desc())
        ).mappings().all()
    return [dict(row) for row in rows]


def obter_pdf_documento(documento_id: int) -> tuple[bytes, str, str]:
    sincronizar_documento(documento_id)
    with transacao() as conn:
        row = conn.execute(
            select(DOCUMENTOS_MANUTENCAO).where(DOCUMENTOS_MANUTENCAO.c.id == int(documento_id))
        ).mappings().first()
    if not row:
        raise DocumentoManutencaoError("Documento final não encontrado.")
    if row.get("storage_path"):
        pdf = _storage_requisicao("GET", row["storage_path"])
    elif row.get("pdf_arquivo"):
        pdf = bytes(row["pdf_arquivo"])
    else:
        raise DocumentoManutencaoError("Documento final indisponível.")
    if hashlib.sha256(pdf).hexdigest() != row["hash_documento"]:
        raise DocumentoManutencaoError("A integridade do documento não pôde ser confirmada.")
    return pdf, row["nome_arquivo"], row["hash_documento"]
