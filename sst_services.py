from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from database import registrar_auditoria, transacao, utcnow
from sst_database import (
    ASSINATURAS_SST,
    COLABORADORES,
    DOCUMENTOS_SST,
    ENTREGAS_EPI,
    EPIS,
    ITENS_ENTREGA_EPI,
)


class RegraSSTError(ValueError):
    pass


def _nivel(actor: dict) -> float:
    try:
        return float(actor["nivel"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RegraSSTError("Usuário inválido para o módulo SST.") from exc


def _pode_operar_sst(actor: dict) -> bool:
    # Regra inicial da branch de desenvolvimento.
    # Antes de produção, poderá ser substituída por permissões próprias do módulo SST.
    return _nivel(actor) >= 3.0


def _pode_administrar_sst(actor: dict) -> bool:
    return _nivel(actor) >= 3.5


def _exigir_operacao(actor: dict) -> None:
    if not _pode_operar_sst(actor):
        raise RegraSSTError("Sem permissão para operar o módulo SST.")


def _exigir_administracao(actor: dict) -> None:
    if not _pode_administrar_sst(actor):
        raise RegraSSTError("Sem permissão para administrar o módulo SST.")


def _texto(valor: str | None, limite: int, obrigatorio: bool = False) -> str | None:
    texto = " ".join(str(valor or "").strip().split())
    if obrigatorio and not texto:
        raise RegraSSTError("Preencha todos os campos obrigatórios.")
    if len(texto) > limite:
        raise RegraSSTError("Um dos campos excede o tamanho permitido.")
    return texto or None


def _cpf_normalizado(cpf: str | None) -> str | None:
    if not cpf:
        return None
    digitos = re.sub(r"\D", "", str(cpf))
    if len(digitos) != 11:
        raise RegraSSTError("CPF deve conter 11 dígitos.")
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def _colaborador(conn, colaborador_id: int):
    return conn.execute(
        select(COLABORADORES).where(COLABORADORES.c.id == int(colaborador_id))
    ).mappings().first()


def _epi(conn, epi_id: int):
    return conn.execute(select(EPIS).where(EPIS.c.id == int(epi_id))).mappings().first()


def cadastrar_colaborador(
    actor: dict,
    nome: str,
    funcao: str,
    matricula: str | None = None,
    cpf: str | None = None,
    setor: str | None = None,
    data_admissao=None,
) -> int:
    _exigir_administracao(actor)
    nome = _texto(nome, 160, True)
    funcao = _texto(funcao, 160, True)
    matricula = _texto(matricula, 40)
    cpf = _cpf_normalizado(cpf)
    setor = _texto(setor, 160)
    now = utcnow()

    try:
        with transacao() as conn:
            result = conn.execute(insert(COLABORADORES).values(
                matricula=matricula,
                nome=nome,
                cpf=cpf,
                funcao=funcao,
                setor=setor,
                data_admissao=data_admissao,
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            ))
            colaborador_id = int(result.inserted_primary_key[0])
            registrar_auditoria(
                conn, actor["usuario"], "SST_COLABORADOR_CRIADO",
                "sst_colaborador", str(colaborador_id), f"nome={nome};funcao={funcao}"
            )
            return colaborador_id
    except IntegrityError as exc:
        raise RegraSSTError("Já existe colaborador com essa matrícula ou CPF.") from exc


def listar_colaboradores(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(COLABORADORES)
    if apenas_ativos:
        stmt = stmt.where(COLABORADORES.c.ativo == True)
    stmt = stmt.order_by(COLABORADORES.c.nome)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def desativar_colaborador(actor: dict, colaborador_id: int) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        row = _colaborador(conn, colaborador_id)
        if not row:
            raise RegraSSTError("Colaborador não encontrado.")
        if not row["ativo"]:
            raise RegraSSTError("Colaborador já está desativado.")
        conn.execute(update(COLABORADORES).where(
            COLABORADORES.c.id == int(colaborador_id)
        ).values(ativo=False, atualizado_em=utcnow()))
        registrar_auditoria(
            conn, actor["usuario"], "SST_COLABORADOR_DESATIVADO",
            "sst_colaborador", str(colaborador_id)
        )


def cadastrar_epi(
    actor: dict,
    nome: str,
    ca: str | None = None,
    fabricante: str | None = None,
    unidade: str = "unidade",
) -> int:
    _exigir_administracao(actor)
    nome = _texto(nome, 180, True)
    ca = _texto(ca, 40)
    fabricante = _texto(fabricante, 160)
    unidade = _texto(unidade, 40, True)
    now = utcnow()

    try:
        with transacao() as conn:
            result = conn.execute(insert(EPIS).values(
                nome=nome,
                ca=ca,
                fabricante=fabricante,
                unidade=unidade,
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            ))
            epi_id = int(result.inserted_primary_key[0])
            registrar_auditoria(
                conn, actor["usuario"], "SST_EPI_CRIADO",
                "sst_epi", str(epi_id), f"nome={nome};ca={ca or ''}"
            )
            return epi_id
    except IntegrityError as exc:
        raise RegraSSTError("Esse EPI/CA já está cadastrado.") from exc


def listar_epis(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(EPIS)
    if apenas_ativos:
        stmt = stmt.where(EPIS.c.ativo == True)
    stmt = stmt.order_by(EPIS.c.nome)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def registrar_entrega_epi(
    actor: dict,
    colaborador_id: int,
    itens: Iterable[dict],
    observacao: str | None = None,
) -> int:
    _exigir_operacao(actor)
    itens = list(itens)
    if not itens:
        raise RegraSSTError("Inclua pelo menos um EPI na entrega.")
    observacao = _texto(observacao, 2000)
    now = utcnow()

    with transacao() as conn:
        colaborador = _colaborador(conn, colaborador_id)
        if not colaborador or not colaborador["ativo"]:
            raise RegraSSTError("Colaborador indisponível para entrega.")

        preparados = []
        for item in itens:
            epi_id = int(item.get("epi_id", 0))
            quantidade = int(item.get("quantidade", 0))
            if quantidade <= 0 or quantidade > 1000:
                raise RegraSSTError("Quantidade de EPI inválida.")
            epi = _epi(conn, epi_id)
            if not epi or not epi["ativo"]:
                raise RegraSSTError("Um dos EPIs está indisponível.")
            preparados.append((epi, quantidade))

        result = conn.execute(insert(ENTREGAS_EPI).values(
            colaborador_id=int(colaborador_id),
            responsavel_usuario=actor["usuario"],
            entregue_em=now,
            observacao=observacao,
            status="Registrada",
            criado_em=now,
        ))
        entrega_id = int(result.inserted_primary_key[0])

        for epi, quantidade in preparados:
            conn.execute(insert(ITENS_ENTREGA_EPI).values(
                entrega_id=entrega_id,
                epi_id=int(epi["id"]),
                quantidade=quantidade,
                ca_no_momento=epi["ca"],
            ))

        registrar_auditoria(
            conn, actor["usuario"], "SST_EPI_ENTREGUE",
            "sst_entrega_epi", str(entrega_id),
            f"colaborador_id={colaborador_id};itens={len(preparados)}"
        )
        return entrega_id


def criar_documento_sst(
    actor: dict,
    colaborador_id: int,
    tipo: str,
    motivo: str,
    titulo: str,
    conteudo: dict | str,
) -> int:
    _exigir_operacao(actor)
    tipo = _texto(tipo, 80, True)
    motivo = _texto(motivo, 80)
    titulo = _texto(titulo, 220, True)
    snapshot = conteudo if isinstance(conteudo, str) else json.dumps(
        conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if len(snapshot) > 200_000:
        raise RegraSSTError("Conteúdo do documento excede o limite permitido.")

    with transacao() as conn:
        colaborador = _colaborador(conn, colaborador_id)
        if not colaborador or not colaborador["ativo"]:
            raise RegraSSTError("Colaborador indisponível.")

        # O número usa o próximo ID da própria tabela, evitando alterar o contador
        # das OS de manutenção.
        result = conn.execute(insert(DOCUMENTOS_SST).values(
            numero=f"TEMP-{utcnow().timestamp()}",
            colaborador_id=int(colaborador_id),
            tipo=tipo,
            motivo=motivo,
            titulo=titulo,
            conteudo_snapshot=snapshot,
            hash_documento=None,
            status="Rascunho",
            criado_por=actor["usuario"],
            criado_em=utcnow(),
            fechado_em=None,
        ))
        documento_id = int(result.inserted_primary_key[0])
        numero = f"SST-{documento_id:06d}"
        conn.execute(update(DOCUMENTOS_SST).where(
            DOCUMENTOS_SST.c.id == documento_id
        ).values(numero=numero))
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_CRIADO",
            "sst_documento", numero, f"tipo={tipo};motivo={motivo or ''}"
        )
        return documento_id


def fechar_documento_para_assinatura(actor: dict, documento_id: int, pdf_bytes: bytes) -> str:
    _exigir_operacao(actor)
    if not pdf_bytes:
        raise RegraSSTError("PDF do documento não foi informado.")
    hash_documento = hashlib.sha256(pdf_bytes).hexdigest()

    with transacao() as conn:
        row = conn.execute(select(DOCUMENTOS_SST).where(
            DOCUMENTOS_SST.c.id == int(documento_id)
        )).mappings().first()
        if not row:
            raise RegraSSTError("Documento não encontrado.")
        if row["status"] != "Rascunho":
            raise RegraSSTError("Somente documentos em rascunho podem ser fechados.")

        conn.execute(update(DOCUMENTOS_SST).where(
            DOCUMENTOS_SST.c.id == int(documento_id)
        ).values(
            hash_documento=hash_documento,
            status="Aguardando Assinatura",
            fechado_em=utcnow(),
        ))
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_FECHADO",
            "sst_documento", row["numero"], f"sha256={hash_documento}"
        )
    return hash_documento


def registrar_assinatura_biometrica(
    actor: dict,
    documento_id: int,
    colaborador_id: int,
    referencia_biometrica: str,
    estacao: str | None = None,
    detalhes: str | None = None,
) -> int:
    """Registra o RESULTADO de uma validação biométrica futura.

    Esta função não captura nem compara digitais. Isso será responsabilidade do
    componente local/SDK do leitor. Ela só deve ser chamada após o integrador
    biométrico confirmar a identidade do colaborador.
    """
    _exigir_operacao(actor)
    referencia_biometrica = _texto(referencia_biometrica, 255, True)
    estacao = _texto(estacao, 160)
    detalhes = _texto(detalhes, 2000)

    with transacao() as conn:
        doc = conn.execute(select(DOCUMENTOS_SST).where(
            DOCUMENTOS_SST.c.id == int(documento_id)
        )).mappings().first()
        if not doc:
            raise RegraSSTError("Documento não encontrado.")
        if doc["status"] != "Aguardando Assinatura" or not doc["hash_documento"]:
            raise RegraSSTError("Documento não está disponível para assinatura.")
        if int(doc["colaborador_id"]) != int(colaborador_id):
            raise RegraSSTError("A biometria confirmada não pertence ao titular do documento.")

        result = conn.execute(insert(ASSINATURAS_SST).values(
            documento_id=int(documento_id),
            colaborador_id=int(colaborador_id),
            metodo="Biometria",
            status="Confirmada",
            hash_documento=doc["hash_documento"],
            assinado_em=utcnow(),
            estacao=estacao,
            referencia_biometrica=referencia_biometrica,
            detalhes=detalhes,
        ))
        assinatura_id = int(result.inserted_primary_key[0])
        conn.execute(update(DOCUMENTOS_SST).where(
            DOCUMENTOS_SST.c.id == int(documento_id)
        ).values(status="Assinado"))
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_ASSINADO_BIOMETRIA",
            "sst_documento", doc["numero"],
            f"assinatura_id={assinatura_id};colaborador_id={colaborador_id}"
        )
        return assinatura_id
