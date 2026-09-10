from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, insert, select, update
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


TZ_BAHIA = ZoneInfo("America/Bahia")


class RegraSSTError(ValueError):
    pass


def _nivel(actor: dict) -> float:
    try:
        return float(actor["nivel"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RegraSSTError("Usuário inválido para o módulo SST.") from exc


def _pode_operar_sst(actor: dict) -> bool:
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


def _cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
        dv = (soma * 10) % 11
        if dv == 10:
            dv = 0
        if dv != int(digitos[tamanho]):
            return False
    return True


def _cpf_normalizado(cpf: str | None) -> str | None:
    if not cpf:
        return None
    digitos = re.sub(r"\D", "", str(cpf))
    if not _cpf_valido(digitos):
        raise RegraSSTError("CPF inválido.")
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def _hoje_bahia() -> date:
    return datetime.now(TZ_BAHIA).date()


def _colaborador(conn, colaborador_id: int):
    return conn.execute(
        select(COLABORADORES).where(COLABORADORES.c.id == int(colaborador_id))
    ).mappings().first()


def _epi(conn, epi_id: int):
    return conn.execute(
        select(EPIS).where(EPIS.c.id == int(epi_id))
    ).mappings().first()


def _desativar_epis_ca_vencido(conn) -> int:
    hoje = _hoje_bahia()
    result = conn.execute(
        update(EPIS)
        .where(
            EPIS.c.ativo == True,
            EPIS.c.validade_ca.is_not(None),
            EPIS.c.validade_ca < hoje,
        )
        .values(ativo=False, atualizado_em=utcnow())
    )
    return int(result.rowcount or 0)


def sincronizar_cas_vencidos() -> int:
    """Fallback da aplicação: inativa CAs vencidos quando o backend SST é executado.

    A automação definitiva fica no PostgreSQL (ver supabase_cron_sst.sql), então
    esta função é uma segunda barreira de segurança e não depende da interface de EPIs.
    """
    with transacao() as conn:
        return _desativar_epis_ca_vencido(conn)


def obter_resumo_dashboard_sst() -> dict:
    """Retorna somente os agregados do dashboard, sem carregar tabelas inteiras."""
    hoje = _hoje_bahia()
    fim_ca = hoje + timedelta(days=30)
    limite_entregas = utcnow() - timedelta(days=30)

    with transacao() as conn:
        _desativar_epis_ca_vencido(conn)

        colaboradores_ativos = conn.execute(
            select(func.count()).select_from(COLABORADORES).where(COLABORADORES.c.ativo == True)
        ).scalar_one()
        epis_ativos = conn.execute(
            select(func.count()).select_from(EPIS).where(EPIS.c.ativo == True)
        ).scalar_one()
        ca_vencendo = conn.execute(
            select(func.count()).select_from(EPIS).where(
                EPIS.c.ativo == True,
                EPIS.c.validade_ca.is_not(None),
                EPIS.c.validade_ca >= hoje,
                EPIS.c.validade_ca <= fim_ca,
            )
        ).scalar_one()
        entregas_30 = conn.execute(
            select(func.count()).select_from(ENTREGAS_EPI).where(
                ENTREGAS_EPI.c.entregue_em >= limite_entregas
            )
        ).scalar_one()
        aguardando_assinatura = conn.execute(
            select(func.count()).select_from(DOCUMENTOS_SST).where(
                DOCUMENTOS_SST.c.status == "Aguardando Assinatura"
            )
        ).scalar_one()

        status_rows = conn.execute(
            select(DOCUMENTOS_SST.c.status, func.count().label("quantidade"))
            .group_by(DOCUMENTOS_SST.c.status)
            .order_by(DOCUMENTOS_SST.c.status)
        ).mappings().all()

    return {
        "colaboradores_ativos": int(colaboradores_ativos or 0),
        "epis_ativos": int(epis_ativos or 0),
        "ca_vencendo_30": int(ca_vencendo or 0),
        "entregas_30": int(entregas_30 or 0),
        "aguardando_assinatura": int(aguardando_assinatura or 0),
        "documentos_por_status": [dict(r) for r in status_rows],
    }


def cadastrar_colaborador(
    actor: dict,
    nome: str,
    funcao: str,
    matricula: str | None = None,
    cpf: str | None = None,
    setor: str | None = None,
    data_admissao: date | None = None,
) -> int:
    _exigir_administracao(actor)
    nome = _texto(nome, 160, True)
    funcao = _texto(funcao, 160, True)
    matricula = _texto(matricula, 40)
    cpf = _cpf_normalizado(cpf)
    setor = _texto(setor, 160)
    if data_admissao and data_admissao > _hoje_bahia():
        raise RegraSSTError("A data de admissão não pode estar no futuro.")
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
                "sst_colaborador", str(colaborador_id),
                f"nome={nome};funcao={funcao}"
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


def definir_status_colaborador(actor: dict, colaborador_id: int, ativo: bool) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        row = _colaborador(conn, colaborador_id)
        if not row:
            raise RegraSSTError("Colaborador não encontrado.")
        if bool(row["ativo"]) == bool(ativo):
            raise RegraSSTError("O colaborador já está com esse status.")
        conn.execute(
            update(COLABORADORES)
            .where(COLABORADORES.c.id == int(colaborador_id))
            .values(ativo=bool(ativo), atualizado_em=utcnow())
        )
        acao = "SST_COLABORADOR_REATIVADO" if ativo else "SST_COLABORADOR_DESATIVADO"
        registrar_auditoria(
            conn, actor["usuario"], acao, "sst_colaborador", str(colaborador_id)
        )


def cadastrar_epi(
    actor: dict,
    nome: str,
    ca: str,
    fabricante: str | None = None,
    unidade: str = "unidade",
    validade_ca: date | None = None,
) -> int:
    _exigir_administracao(actor)
    nome = _texto(nome, 180, True)
    ca = _texto(ca, 40, True)
    fabricante = _texto(fabricante, 160)
    unidade = _texto(unidade, 40, True)
    if validade_ca is None:
        raise RegraSSTError("Informe a validade do CA.")
    if validade_ca < _hoje_bahia():
        raise RegraSSTError("A validade do CA não pode estar vencida no cadastro.")
    now = utcnow()

    try:
        with transacao() as conn:
            result = conn.execute(insert(EPIS).values(
                nome=nome,
                ca=ca,
                fabricante=fabricante,
                validade_ca=validade_ca,
                unidade=unidade,
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            ))
            epi_id = int(result.inserted_primary_key[0])
            registrar_auditoria(
                conn, actor["usuario"], "SST_EPI_CRIADO",
                "sst_epi", str(epi_id),
                f"nome={nome};ca={ca};validade_ca={validade_ca}"
            )
            return epi_id
    except IntegrityError as exc:
        raise RegraSSTError("Esse EPI/CA já está cadastrado.") from exc


def listar_epis(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(EPIS)
    if apenas_ativos:
        stmt = stmt.where(EPIS.c.ativo == True)
    stmt = stmt.order_by(EPIS.c.nome, EPIS.c.ca)
    with transacao() as conn:
        _desativar_epis_ca_vencido(conn)
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def atualizar_validade_epi(
    actor: dict,
    epi_id: int,
    nova_validade: date,
    reativar: bool = True,
) -> None:
    _exigir_administracao(actor)
    if nova_validade < _hoje_bahia():
        raise RegraSSTError("A nova validade do CA não pode estar vencida.")
    with transacao() as conn:
        epi = _epi(conn, epi_id)
        if not epi:
            raise RegraSSTError("EPI não encontrado.")
        valores = {"validade_ca": nova_validade, "atualizado_em": utcnow()}
        if reativar:
            valores["ativo"] = True
        conn.execute(
            update(EPIS).where(EPIS.c.id == int(epi_id)).values(**valores)
        )
        registrar_auditoria(
            conn, actor["usuario"], "SST_EPI_CA_ATUALIZADO",
            "sst_epi", str(epi_id),
            f"ca={epi['ca']};validade_antiga={epi['validade_ca']};nova_validade={nova_validade};reativado={reativar}"
        )


def definir_status_epi(actor: dict, epi_id: int, ativo: bool) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        epi = _epi(conn, epi_id)
        if not epi:
            raise RegraSSTError("EPI não encontrado.")
        if ativo and epi["validade_ca"] and epi["validade_ca"] < _hoje_bahia():
            raise RegraSSTError("Atualize a validade do CA antes de reativar este EPI.")
        if bool(epi["ativo"]) == bool(ativo):
            raise RegraSSTError("O EPI já está com esse status.")
        conn.execute(
            update(EPIS)
            .where(EPIS.c.id == int(epi_id))
            .values(ativo=bool(ativo), atualizado_em=utcnow())
        )
        acao = "SST_EPI_REATIVADO" if ativo else "SST_EPI_DESATIVADO"
        registrar_auditoria(conn, actor["usuario"], acao, "sst_epi", str(epi_id))


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
    if len(itens) > 10:
        raise RegraSSTError("Uma entrega pode conter no máximo 10 itens.")
    observacao = _texto(observacao, 2000)
    now = utcnow()

    ids = []
    for item in itens:
        epi_id = int(item.get("epi_id", 0))
        if epi_id in ids:
            raise RegraSSTError("O mesmo EPI foi selecionado mais de uma vez.")
        ids.append(epi_id)

    with transacao() as conn:
        _desativar_epis_ca_vencido(conn)
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
                raise RegraSSTError("Um dos EPIs está indisponível ou possui CA vencido.")
            if epi["validade_ca"] is None:
                raise RegraSSTError("Um dos EPIs não possui validade de CA informada.")
            if epi["validade_ca"] < _hoje_bahia():
                raise RegraSSTError("Não é permitido entregar EPI com CA vencido.")
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

        itens_snapshot = []
        for epi, quantidade in preparados:
            conn.execute(insert(ITENS_ENTREGA_EPI).values(
                entrega_id=entrega_id,
                epi_id=int(epi["id"]),
                quantidade=quantidade,
                ca_no_momento=epi["ca"],
                validade_ca_no_momento=epi["validade_ca"],
            ))
            itens_snapshot.append({
                "epi_id": int(epi["id"]),
                "nome": epi["nome"],
                "ca": epi["ca"],
                "validade_ca": epi["validade_ca"].isoformat() if epi["validade_ca"] else None,
                "unidade": epi["unidade"],
                "quantidade": quantidade,
            })

        # Cada entrega gera um documento próprio para futura assinatura biométrica.
        doc_result = conn.execute(insert(DOCUMENTOS_SST).values(
            numero=f"TEMP-{utcnow().timestamp()}",
            colaborador_id=int(colaborador_id),
            tipo="Entrega de EPI",
            motivo="Entrega",
            titulo=f"Comprovante de Entrega de EPI #{entrega_id}",
            conteudo_snapshot=json.dumps({
                "entrega_id": entrega_id,
                "colaborador": {
                    "id": int(colaborador["id"]),
                    "nome": colaborador["nome"],
                    "matricula": colaborador["matricula"],
                    "funcao": colaborador["funcao"],
                    "setor": colaborador["setor"],
                },
                "itens": itens_snapshot,
                "observacao": observacao,
                "responsavel_usuario": actor["usuario"],
                "entregue_em": now.isoformat(),
            }, ensure_ascii=False, sort_keys=True),
            hash_documento=None,
            pdf_arquivo=None,
            nome_arquivo=None,
            status="Rascunho",
            criado_por=actor["usuario"],
            criado_em=now,
            fechado_em=None,
        ))
        documento_id = int(doc_result.inserted_primary_key[0])
        numero = f"SST-{documento_id:06d}"
        conn.execute(
            update(DOCUMENTOS_SST)
            .where(DOCUMENTOS_SST.c.id == documento_id)
            .values(numero=numero)
        )

        registrar_auditoria(
            conn, actor["usuario"], "SST_EPI_ENTREGUE",
            "sst_entrega_epi", str(entrega_id),
            f"colaborador_id={colaborador_id};itens={len(preparados)};documento={numero}"
        )
        return entrega_id


def listar_entregas(limite: int = 200) -> list[dict]:
    limite = max(1, min(int(limite), 1000))
    stmt = (
        select(
            ENTREGAS_EPI.c.id.label("entrega_id"),
            ENTREGAS_EPI.c.entregue_em,
            ENTREGAS_EPI.c.observacao,
            ENTREGAS_EPI.c.responsavel_usuario,
            COLABORADORES.c.nome.label("colaborador"),
            COLABORADORES.c.matricula.label("matricula"),
            EPIS.c.nome.label("epi"),
            ITENS_ENTREGA_EPI.c.ca_no_momento.label("ca"),
            ITENS_ENTREGA_EPI.c.validade_ca_no_momento.label("validade_ca"),
            ITENS_ENTREGA_EPI.c.quantidade,
        )
        .select_from(
            ENTREGAS_EPI
            .join(COLABORADORES, ENTREGAS_EPI.c.colaborador_id == COLABORADORES.c.id)
            .join(ITENS_ENTREGA_EPI, ITENS_ENTREGA_EPI.c.entrega_id == ENTREGAS_EPI.c.id)
            .join(EPIS, ITENS_ENTREGA_EPI.c.epi_id == EPIS.c.id)
        )
        .order_by(ENTREGAS_EPI.c.entregue_em.desc(), ITENS_ENTREGA_EPI.c.id.asc())
        .limit(limite)
    )
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def criar_documento_sst(
    actor: dict,
    colaborador_id: int,
    tipo: str,
    motivo: str | None,
    titulo: str,
    conteudo: dict | str,
) -> int:
    _exigir_operacao(actor)
    tipo = _texto(tipo, 80, True)
    motivo = _texto(motivo, 80)
    titulo = _texto(titulo, 220, True)
    snapshot = conteudo if isinstance(conteudo, str) else json.dumps(
        conteudo, ensure_ascii=False, sort_keys=True
    )
    if len(snapshot) > 200_000:
        raise RegraSSTError("Conteúdo do documento excede o limite permitido.")

    with transacao() as conn:
        colaborador = _colaborador(conn, colaborador_id)
        if not colaborador or not colaborador["ativo"]:
            raise RegraSSTError("Colaborador indisponível.")

        result = conn.execute(insert(DOCUMENTOS_SST).values(
            numero=f"TEMP-{utcnow().timestamp()}",
            colaborador_id=int(colaborador_id),
            tipo=tipo,
            motivo=motivo,
            titulo=titulo,
            conteudo_snapshot=snapshot,
            hash_documento=None,
            pdf_arquivo=None,
            nome_arquivo=None,
            status="Rascunho",
            criado_por=actor["usuario"],
            criado_em=utcnow(),
            fechado_em=None,
        ))
        documento_id = int(result.inserted_primary_key[0])
        numero = f"SST-{documento_id:06d}"
        conn.execute(
            update(DOCUMENTOS_SST)
            .where(DOCUMENTOS_SST.c.id == documento_id)
            .values(numero=numero)
        )
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_CRIADO",
            "sst_documento", numero, f"tipo={tipo};motivo={motivo or ''}"
        )
        return documento_id


def obter_documento(documento_id: int) -> dict:
    stmt = (
        select(
            DOCUMENTOS_SST,
            COLABORADORES.c.nome.label("colaborador"),
            COLABORADORES.c.matricula.label("matricula"),
            COLABORADORES.c.funcao.label("funcao"),
            COLABORADORES.c.setor.label("setor"),
        )
        .select_from(
            DOCUMENTOS_SST.join(
                COLABORADORES,
                DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id,
            )
        )
        .where(DOCUMENTOS_SST.c.id == int(documento_id))
    )
    with transacao() as conn:
        row = conn.execute(stmt).mappings().first()
        if not row:
            raise RegraSSTError("Documento não encontrado.")
        return dict(row)


def fechar_documento_para_assinatura(
    actor: dict,
    documento_id: int,
    pdf_bytes: bytes,
    nome_arquivo: str,
) -> str:
    _exigir_operacao(actor)
    if not pdf_bytes:
        raise RegraSSTError("PDF do documento não foi informado.")
    if len(pdf_bytes) > 10_000_000:
        raise RegraSSTError("O PDF excede o limite de 10 MB.")
    nome_arquivo = _texto(nome_arquivo, 255, True)
    hash_documento = hashlib.sha256(pdf_bytes).hexdigest()

    with transacao() as conn:
        row = conn.execute(
            select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id))
        ).mappings().first()
        if not row:
            raise RegraSSTError("Documento não encontrado.")
        if row["status"] != "Rascunho":
            raise RegraSSTError("Somente documentos em rascunho podem ser fechados.")

        conn.execute(
            update(DOCUMENTOS_SST)
            .where(DOCUMENTOS_SST.c.id == int(documento_id))
            .values(
                hash_documento=hash_documento,
                pdf_arquivo=pdf_bytes,
                nome_arquivo=nome_arquivo,
                status="Aguardando Assinatura",
                fechado_em=utcnow(),
            )
        )
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_FECHADO",
            "sst_documento", row["numero"], f"sha256={hash_documento}"
        )
    return hash_documento


def obter_pdf_documento(documento_id: int) -> tuple[bytes, str, str]:
    with transacao() as conn:
        row = conn.execute(
            select(
                DOCUMENTOS_SST.c.pdf_arquivo,
                DOCUMENTOS_SST.c.nome_arquivo,
                DOCUMENTOS_SST.c.hash_documento,
            ).where(DOCUMENTOS_SST.c.id == int(documento_id))
        ).mappings().first()
        if not row or not row["pdf_arquivo"]:
            raise RegraSSTError("Este documento ainda não possui PDF fechado.")
        return bytes(row["pdf_arquivo"]), row["nome_arquivo"], row["hash_documento"]


def listar_documentos(limite: int = 200) -> list[dict]:
    limite = max(1, min(int(limite), 1000))
    stmt = (
        select(
            DOCUMENTOS_SST.c.id,
            DOCUMENTOS_SST.c.numero,
            DOCUMENTOS_SST.c.tipo,
            DOCUMENTOS_SST.c.motivo,
            DOCUMENTOS_SST.c.titulo,
            DOCUMENTOS_SST.c.status,
            DOCUMENTOS_SST.c.criado_em,
            DOCUMENTOS_SST.c.fechado_em,
            DOCUMENTOS_SST.c.hash_documento,
            DOCUMENTOS_SST.c.nome_arquivo,
            COLABORADORES.c.nome.label("colaborador"),
            COLABORADORES.c.matricula.label("matricula"),
        )
        .select_from(
            DOCUMENTOS_SST.join(
                COLABORADORES,
                DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id,
            )
        )
        .order_by(DOCUMENTOS_SST.c.criado_em.desc())
        .limit(limite)
    )
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def listar_pendentes_assinatura(limite: int = 200) -> list[dict]:
    stmt = (
        select(
            DOCUMENTOS_SST.c.id,
            DOCUMENTOS_SST.c.numero,
            DOCUMENTOS_SST.c.tipo,
            DOCUMENTOS_SST.c.titulo,
            DOCUMENTOS_SST.c.hash_documento,
            DOCUMENTOS_SST.c.fechado_em,
            COLABORADORES.c.nome.label("colaborador"),
            COLABORADORES.c.matricula.label("matricula"),
        )
        .select_from(
            DOCUMENTOS_SST.join(
                COLABORADORES,
                DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id,
            )
        )
        .where(DOCUMENTOS_SST.c.status == "Aguardando Assinatura")
        .order_by(DOCUMENTOS_SST.c.fechado_em.desc())
        .limit(max(1, min(int(limite), 1000)))
    )
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def registrar_assinatura_biometrica(
    actor: dict,
    documento_id: int,
    colaborador_id: int,
    referencia_biometrica: str,
    estacao: str | None = None,
    detalhes: str | None = None,
) -> int:
    """Registra apenas o resultado de uma validação feita pelo SDK biométrico."""
    _exigir_operacao(actor)
    referencia_biometrica = _texto(referencia_biometrica, 255, True)
    estacao = _texto(estacao, 160)
    detalhes = _texto(detalhes, 2000)

    with transacao() as conn:
        doc = conn.execute(
            select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id))
        ).mappings().first()
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
        conn.execute(
            update(DOCUMENTOS_SST)
            .where(DOCUMENTOS_SST.c.id == int(documento_id))
            .values(status="Assinado")
        )
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_ASSINADO_BIOMETRIA",
            "sst_documento", doc["numero"],
            f"assinatura_id={assinatura_id};colaborador_id={colaborador_id}"
        )
        return assinatura_id
