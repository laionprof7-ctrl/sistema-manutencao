from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from database import ENGINE, registrar_auditoria, transacao, utcnow
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

TZ_BAHIA = ZoneInfo("America/Bahia")
MOTIVOS_ENTREGA = ("Primeira entrega", "Desgaste do equipamento anterior", "Perda")
MOTIVOS_OS = ("Admissão", "Mudança de função", "Serviço eventual")

STORAGE_BUCKET_SST = "documentos-sst"
STORAGE_LIMITE_BYTES = 10 * 1024 * 1024


def _segredo_storage(nome: str) -> str:
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
    raise RegraSSTError(f"Configuração {nome} não encontrada nos Secrets do aplicativo.")


def _storage_config() -> tuple[str, str]:
    url = _segredo_storage("SUPABASE_URL").rstrip("/")
    # O endpoint REST do Storage exige um JWT no header Authorization.
    # Por compatibilidade com o Storage atual, usamos a chave legacy service_role
    # somente no backend do Streamlit. Ela nunca deve ir para GitHub ou navegador.
    chave = _segredo_storage("SUPABASE_SERVICE_ROLE_KEY")
    if not url.startswith("https://"):
        raise RegraSSTError("SUPABASE_URL inválida nos Secrets do aplicativo.")
    return url, chave


def _storage_path(numero: str, tipo: str, nome_arquivo: str) -> str:
    partes = str(numero).split("-")
    ano = partes[1] if len(partes) >= 3 and partes[1].isdigit() else str(_hoje_bahia().year)
    if tipo == "Entrega de EPI":
        pasta = "entregas-epi"
    elif tipo == "Ordem de Serviço de SST":
        pasta = "ordens-servico"
    else:
        pasta = "outros"
    nome_seguro = re.sub(r"[^0-9A-Za-zÀ-ÿ_.-]+", "_", str(nome_arquivo)).strip("._") or f"{numero}.pdf"
    return f"{ano}/{pasta}/{nome_seguro}"


def _storage_requisicao(metodo: str, path: str, dados: bytes | None = None) -> bytes:
    url_base, chave = _storage_config()
    caminho = quote(path, safe="/")
    url = f"{url_base}/storage/v1/object/{STORAGE_BUCKET_SST}/{caminho}"
    headers = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "User-Agent": "Copa-SST-Backend/1.0",
    }
    if dados is not None:
        headers["Content-Type"] = "application/pdf"
        headers["x-upsert"] = "false"
    req = Request(url, data=dados, headers=headers, method=metodo)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read()
    except HTTPError as exc:
        try:
            detalhe = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detalhe = ""
        raise RegraSSTError(f"Falha no Storage do SST (HTTP {exc.code}). {detalhe[:300]}") from exc
    except URLError as exc:
        raise RegraSSTError("Não foi possível conectar ao Storage do SST.") from exc


def _storage_enviar(path: str, pdf_bytes: bytes) -> None:
    if not pdf_bytes:
        raise RegraSSTError("PDF do documento não foi informado.")
    if len(pdf_bytes) > STORAGE_LIMITE_BYTES:
        raise RegraSSTError("O PDF excede o limite de 10 MB.")
    _storage_requisicao("POST", path, pdf_bytes)


def _storage_baixar(path: str) -> bytes:
    return _storage_requisicao("GET", path)


def _storage_excluir(path: str) -> None:
    try:
        _storage_requisicao("DELETE", path)
    except Exception:
        pass


def _usar_storage_sst() -> bool:
    # Em produção (PostgreSQL/Supabase), PDFs novos ficam no Storage.
    # SQLite continua suportado para testes locais sem exigir credenciais externas.
    return ENGINE.dialect.name == "postgresql"


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


def _texto_longo(valor: str | None, limite: int = 50_000) -> str | None:
    texto = str(valor or "").strip()
    if len(texto) > limite:
        raise RegraSSTError("Um dos campos de conteúdo excede o tamanho permitido.")
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
    return conn.execute(select(COLABORADORES).where(COLABORADORES.c.id == int(colaborador_id))).mappings().first()


def _epi(conn, epi_id: int):
    return conn.execute(select(EPIS).where(EPIS.c.id == int(epi_id))).mappings().first()


def _ghe(conn, ghe_id: int):
    return conn.execute(select(GHE).where(GHE.c.id == int(ghe_id))).mappings().first()


def _desativar_epis_ca_vencido(conn) -> int:
    hoje = _hoje_bahia()
    result = conn.execute(
        update(EPIS)
        .where(EPIS.c.ativo == True, EPIS.c.validade_ca.is_not(None), EPIS.c.validade_ca < hoje)
        .values(ativo=False, atualizado_em=utcnow())
    )
    return int(result.rowcount or 0)


def sincronizar_cas_vencidos() -> int:
    with transacao() as conn:
        return _desativar_epis_ca_vencido(conn)


def _incrementar_contador(conn, ano: int) -> int:
    chave = f"documentos_{ano}"
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
        conn.execute(dialect_insert(CONTADORES_SST).values(chave=chave, valor=0).on_conflict_do_nothing(index_elements=[CONTADORES_SST.c.chave]))
    elif conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
        conn.execute(dialect_insert(CONTADORES_SST).values(chave=chave, valor=0).on_conflict_do_nothing(index_elements=[CONTADORES_SST.c.chave]))
    valor = conn.execute(
        update(CONTADORES_SST)
        .where(CONTADORES_SST.c.chave == chave)
        .values(valor=CONTADORES_SST.c.valor + 1)
        .returning(CONTADORES_SST.c.valor)
    ).scalar_one_or_none()
    if valor is None:
        raise RegraSSTError("Não foi possível gerar a numeração do documento SST.")
    return int(valor)


def _novo_numero_documento(conn, momento: datetime | None = None) -> str:
    momento = momento or utcnow()
    ano = momento.astimezone(TZ_BAHIA).year if getattr(momento, "tzinfo", None) else _hoje_bahia().year
    sequencial = _incrementar_contador(conn, ano)
    return f"SST-{ano}-{sequencial:07d}"


def _nome_pdf(numero: str, tipo: str) -> str:
    seguro = re.sub(r"[^0-9A-Za-zÀ-ÿ_-]+", "_", tipo).strip("_") or "Documento_SST"
    return f"{numero}_{seguro}.pdf"


def obter_resumo_dashboard_sst() -> dict:
    hoje = _hoje_bahia()
    limite_ca = hoje + timedelta(days=30)
    desde = datetime.now(TZ_BAHIA) - timedelta(days=30)
    desde_utc = desde.astimezone(timezone.utc)
    with transacao() as conn:
        _desativar_epis_ca_vencido(conn)
        colaboradores_ativos = conn.execute(select(func.count()).select_from(COLABORADORES).where(COLABORADORES.c.ativo == True)).scalar()
        epis_ativos = conn.execute(select(func.count()).select_from(EPIS).where(EPIS.c.ativo == True)).scalar()
        ca_vencendo = conn.execute(
            select(func.count()).select_from(EPIS).where(
                EPIS.c.ativo == True,
                EPIS.c.validade_ca.is_not(None),
                EPIS.c.validade_ca >= hoje,
                EPIS.c.validade_ca <= limite_ca,
            )
        ).scalar()
        entregas_30 = conn.execute(select(func.count()).select_from(ENTREGAS_EPI).where(ENTREGAS_EPI.c.entregue_em >= desde_utc)).scalar()
        aguardando = conn.execute(select(func.count()).select_from(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.status == "Aguardando Assinatura")).scalar()
        ghes_ativos = conn.execute(select(func.count()).select_from(GHE).where(GHE.c.ativo == True)).scalar()
        status_rows = conn.execute(
            select(DOCUMENTOS_SST.c.status, func.count().label("quantidade")).group_by(DOCUMENTOS_SST.c.status).order_by(DOCUMENTOS_SST.c.status)
        ).mappings().all()
    return {
        "colaboradores_ativos": int(colaboradores_ativos or 0),
        "epis_ativos": int(epis_ativos or 0),
        "ca_vencendo_30": int(ca_vencendo or 0),
        "entregas_30": int(entregas_30 or 0),
        "aguardando_assinatura": int(aguardando or 0),
        "ghes_ativos": int(ghes_ativos or 0),
        "documentos_por_status": [dict(r) for r in status_rows],
    }


# ------------------------- GHE -------------------------

def cadastrar_ghe(actor: dict, codigo: str, nome: str, setor: str, funcao: str,
                   riscos: str | None = None, medidas_preventivas: str | None = None,
                   epis_recomendados: str | None = None, orientacoes: str | None = None) -> int:
    _exigir_administracao(actor)
    codigo = _texto(codigo, 40, True).upper()
    nome = _texto(nome, 160, True)
    setor = _texto(setor, 160, True)
    funcao = _texto(funcao, 160, True)
    riscos = _texto_longo(riscos)
    medidas_preventivas = _texto_longo(medidas_preventivas)
    epis_recomendados = _texto_longo(epis_recomendados)
    orientacoes = _texto_longo(orientacoes)
    now = utcnow()
    try:
        with transacao() as conn:
            result = conn.execute(insert(GHE).values(
                codigo=codigo, nome=nome, riscos=riscos, medidas_preventivas=medidas_preventivas,
                epis_recomendados=epis_recomendados, orientacoes=orientacoes, ativo=True,
                criado_em=now, atualizado_em=now,
            ))
            ghe_id = int(result.inserted_primary_key[0])
            conn.execute(insert(GHE_VINCULOS).values(ghe_id=ghe_id, setor=setor, funcao=funcao, criado_em=now))
            registrar_auditoria(conn, actor["usuario"], "SST_GHE_CRIADO", "sst_ghe", str(ghe_id), f"codigo={codigo};setor={setor};funcao={funcao}")
            return ghe_id
    except IntegrityError as exc:
        raise RegraSSTError("Já existe GHE com esse código ou esse vínculo de setor/função.") from exc


def adicionar_vinculo_ghe(actor: dict, ghe_id: int, setor: str, funcao: str) -> int:
    _exigir_administracao(actor)
    setor = _texto(setor, 160, True)
    funcao = _texto(funcao, 160, True)
    try:
        with transacao() as conn:
            ghe = _ghe(conn, ghe_id)
            if not ghe:
                raise RegraSSTError("GHE não encontrado.")
            result = conn.execute(insert(GHE_VINCULOS).values(ghe_id=int(ghe_id), setor=setor, funcao=funcao, criado_em=utcnow()))
            vinculo_id = int(result.inserted_primary_key[0])
            registrar_auditoria(conn, actor["usuario"], "SST_GHE_VINCULO_CRIADO", "sst_ghe", str(ghe_id), f"setor={setor};funcao={funcao}")
            return vinculo_id
    except IntegrityError as exc:
        raise RegraSSTError("Esse setor/função já está vinculado ao GHE.") from exc


def atualizar_conteudo_ghe(actor: dict, ghe_id: int, riscos: str | None, medidas_preventivas: str | None,
                           epis_recomendados: str | None, orientacoes: str | None) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        ghe = _ghe(conn, ghe_id)
        if not ghe:
            raise RegraSSTError("GHE não encontrado.")
        conn.execute(update(GHE).where(GHE.c.id == int(ghe_id)).values(
            riscos=_texto_longo(riscos), medidas_preventivas=_texto_longo(medidas_preventivas),
            epis_recomendados=_texto_longo(epis_recomendados), orientacoes=_texto_longo(orientacoes), atualizado_em=utcnow(),
        ))
        registrar_auditoria(conn, actor["usuario"], "SST_GHE_CONTEUDO_ATUALIZADO", "sst_ghe", str(ghe_id))


def definir_status_ghe(actor: dict, ghe_id: int, ativo: bool) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        ghe = _ghe(conn, ghe_id)
        if not ghe:
            raise RegraSSTError("GHE não encontrado.")
        if bool(ghe["ativo"]) == bool(ativo):
            raise RegraSSTError("O GHE já está com esse status.")
        conn.execute(update(GHE).where(GHE.c.id == int(ghe_id)).values(ativo=bool(ativo), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "SST_GHE_REATIVADO" if ativo else "SST_GHE_DESATIVADO", "sst_ghe", str(ghe_id))


def listar_ghes(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(GHE)
    if apenas_ativos:
        stmt = stmt.where(GHE.c.ativo == True)
    stmt = stmt.order_by(GHE.c.codigo, GHE.c.nome)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def listar_vinculos_ghe(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(
        GHE_VINCULOS.c.id.label("vinculo_id"), GHE_VINCULOS.c.ghe_id,
        GHE.c.codigo.label("ghe_codigo"), GHE.c.nome.label("ghe_nome"), GHE.c.ativo.label("ghe_ativo"),
        GHE_VINCULOS.c.setor, GHE_VINCULOS.c.funcao,
    ).select_from(GHE_VINCULOS.join(GHE, GHE_VINCULOS.c.ghe_id == GHE.c.id))
    if apenas_ativos:
        stmt = stmt.where(GHE.c.ativo == True)
    stmt = stmt.order_by(GHE.c.codigo, GHE_VINCULOS.c.setor, GHE_VINCULOS.c.funcao)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


# --------------------- COLABORADORES -------------------

def cadastrar_colaborador(actor: dict, nome: str, funcao: str, matricula: str | None = None,
                           cpf: str | None = None, setor: str | None = None, data_admissao: date | None = None,
                           ghe_id: int | None = None) -> int:
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
            if ghe_id is not None:
                ghe = _ghe(conn, int(ghe_id))
                if not ghe or not ghe["ativo"]:
                    raise RegraSSTError("Selecione um GHE ativo.")
                vinculo = conn.execute(select(GHE_VINCULOS.c.id).where(
                    GHE_VINCULOS.c.ghe_id == int(ghe_id), GHE_VINCULOS.c.setor == setor, GHE_VINCULOS.c.funcao == funcao
                )).scalar_one_or_none()
                if vinculo is None:
                    raise RegraSSTError("Função/setor não pertence ao GHE selecionado.")
            result = conn.execute(insert(COLABORADORES).values(
                matricula=matricula, nome=nome, cpf=cpf, funcao=funcao, setor=setor, ghe_id=ghe_id,
                data_admissao=data_admissao, ativo=True, criado_em=now, atualizado_em=now,
            ))
            colaborador_id = int(result.inserted_primary_key[0])
            registrar_auditoria(conn, actor["usuario"], "SST_COLABORADOR_CRIADO", "sst_colaborador", str(colaborador_id), f"nome={nome};funcao={funcao};ghe_id={ghe_id}")
            return colaborador_id
    except IntegrityError as exc:
        raise RegraSSTError("Já existe colaborador com essa matrícula ou CPF.") from exc


def vincular_colaborador_ghe(actor: dict, colaborador_id: int, ghe_id: int, setor: str, funcao: str) -> None:
    _exigir_administracao(actor)
    setor = _texto(setor, 160, True)
    funcao = _texto(funcao, 160, True)
    with transacao() as conn:
        colab = _colaborador(conn, colaborador_id)
        ghe = _ghe(conn, ghe_id)
        if not colab:
            raise RegraSSTError("Colaborador não encontrado.")
        if not ghe or not ghe["ativo"]:
            raise RegraSSTError("GHE indisponível.")
        vinculo = conn.execute(select(GHE_VINCULOS.c.id).where(
            GHE_VINCULOS.c.ghe_id == int(ghe_id), GHE_VINCULOS.c.setor == setor, GHE_VINCULOS.c.funcao == funcao
        )).scalar_one_or_none()
        if vinculo is None:
            raise RegraSSTError("Função/setor não pertence ao GHE selecionado.")
        conn.execute(update(COLABORADORES).where(COLABORADORES.c.id == int(colaborador_id)).values(
            ghe_id=int(ghe_id), setor=setor, funcao=funcao, atualizado_em=utcnow()
        ))
        registrar_auditoria(conn, actor["usuario"], "SST_COLABORADOR_GHE_ATUALIZADO", "sst_colaborador", str(colaborador_id), f"ghe={ghe['codigo']};setor={setor};funcao={funcao}")


def listar_colaboradores(apenas_ativos: bool = True) -> list[dict]:
    stmt = select(
        COLABORADORES,
        GHE.c.codigo.label("ghe_codigo"), GHE.c.nome.label("ghe_nome"),
    ).select_from(COLABORADORES.outerjoin(GHE, COLABORADORES.c.ghe_id == GHE.c.id))
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
        conn.execute(update(COLABORADORES).where(COLABORADORES.c.id == int(colaborador_id)).values(ativo=bool(ativo), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "SST_COLABORADOR_REATIVADO" if ativo else "SST_COLABORADOR_DESATIVADO", "sst_colaborador", str(colaborador_id))


# --------------------------- EPI ------------------------

def cadastrar_epi(actor: dict, nome: str, ca: str, fabricante: str | None = None,
                   unidade: str = "unidade", validade_ca: date | None = None) -> int:
    _exigir_administracao(actor)
    nome = _texto(nome, 180, True); ca = _texto(ca, 40, True); fabricante = _texto(fabricante, 160); unidade = _texto(unidade, 40, True)
    if validade_ca is None:
        raise RegraSSTError("Informe a validade do CA.")
    if validade_ca < _hoje_bahia():
        raise RegraSSTError("A validade do CA não pode estar vencida no cadastro.")
    now = utcnow()
    try:
        with transacao() as conn:
            result = conn.execute(insert(EPIS).values(nome=nome, ca=ca, fabricante=fabricante, validade_ca=validade_ca, unidade=unidade, ativo=True, criado_em=now, atualizado_em=now))
            epi_id = int(result.inserted_primary_key[0])
            registrar_auditoria(conn, actor["usuario"], "SST_EPI_CRIADO", "sst_epi", str(epi_id), f"nome={nome};ca={ca};validade_ca={validade_ca}")
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


def atualizar_validade_epi(actor: dict, epi_id: int, nova_validade: date, reativar: bool = True) -> None:
    _exigir_administracao(actor)
    if nova_validade < _hoje_bahia():
        raise RegraSSTError("A nova validade do CA não pode estar vencida.")
    with transacao() as conn:
        epi = _epi(conn, epi_id)
        if not epi: raise RegraSSTError("EPI não encontrado.")
        valores = {"validade_ca": nova_validade, "atualizado_em": utcnow()}
        if reativar: valores["ativo"] = True
        conn.execute(update(EPIS).where(EPIS.c.id == int(epi_id)).values(**valores))
        registrar_auditoria(conn, actor["usuario"], "SST_EPI_CA_ATUALIZADO", "sst_epi", str(epi_id), f"ca={epi['ca']};validade_antiga={epi['validade_ca']};nova_validade={nova_validade};reativado={reativar}")


def definir_status_epi(actor: dict, epi_id: int, ativo: bool) -> None:
    _exigir_administracao(actor)
    with transacao() as conn:
        epi = _epi(conn, epi_id)
        if not epi: raise RegraSSTError("EPI não encontrado.")
        if ativo and epi["validade_ca"] and epi["validade_ca"] < _hoje_bahia():
            raise RegraSSTError("Atualize a validade do CA antes de reativar este EPI.")
        if bool(epi["ativo"]) == bool(ativo): raise RegraSSTError("O EPI já está com esse status.")
        conn.execute(update(EPIS).where(EPIS.c.id == int(epi_id)).values(ativo=bool(ativo), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "SST_EPI_REATIVADO" if ativo else "SST_EPI_DESATIVADO", "sst_epi", str(epi_id))


# ---------------------- DOCUMENTOS ----------------------

def _snapshot_colaborador(colaborador: dict, ghe: dict | None = None) -> dict:
    return {
        "id": int(colaborador["id"]), "nome": colaborador["nome"], "matricula": colaborador.get("matricula"),
        "cpf": colaborador.get("cpf"), "funcao": colaborador.get("funcao"), "setor": colaborador.get("setor"),
        "data_admissao": colaborador.get("data_admissao").isoformat() if colaborador.get("data_admissao") else None,
        "ghe": ({"id": int(ghe["id"]), "codigo": ghe["codigo"], "nome": ghe["nome"]} if ghe else None),
    }


def criar_ordem_servico_sst(actor: dict, colaborador_id: int, motivo: str) -> int:
    _exigir_operacao(actor)
    if motivo not in MOTIVOS_OS:
        raise RegraSSTError("Motivo de emissão da OS inválido.")
    now = utcnow()
    with transacao() as conn:
        colaborador = _colaborador(conn, colaborador_id)
        if not colaborador or not colaborador["ativo"]:
            raise RegraSSTError("Colaborador indisponível.")
        if not colaborador.get("ghe_id"):
            raise RegraSSTError("Vincule um GHE ao colaborador antes de emitir a Ordem de Serviço.")
        ghe = _ghe(conn, int(colaborador["ghe_id"]))
        if not ghe or not ghe["ativo"]:
            raise RegraSSTError("O GHE vinculado ao colaborador está indisponível.")
        numero = _novo_numero_documento(conn, now)
        snapshot = {
            "modelo": "ordem_servico_sst",
            "colaborador": _snapshot_colaborador(dict(colaborador), dict(ghe)),
            "ghe_conteudo": {
                "riscos": ghe.get("riscos"), "medidas_preventivas": ghe.get("medidas_preventivas"),
                "epis_recomendados": ghe.get("epis_recomendados"), "orientacoes": ghe.get("orientacoes"),
            },
            "motivo_emissao": motivo,
        }
        result = conn.execute(insert(DOCUMENTOS_SST).values(
            numero=numero, colaborador_id=int(colaborador_id), entrega_id=None, tipo="Ordem de Serviço de SST",
            motivo=motivo, titulo=f"Ordem de Serviço de SST — {motivo}", conteudo_snapshot=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            hash_documento=None, pdf_arquivo=None, nome_arquivo=None, status="Rascunho",
            criado_por=actor["usuario"], criado_em=now, fechado_em=None,
        ))
        documento_id = int(result.inserted_primary_key[0])
        registrar_auditoria(conn, actor["usuario"], "SST_DOCUMENTO_CRIADO", "sst_documento", numero, f"tipo=Ordem de Serviço de SST;motivo={motivo};ghe={ghe['codigo']}")
        return documento_id


def criar_documento_sst(actor: dict, colaborador_id: int, tipo: str, motivo: str | None, titulo: str, conteudo: dict | str) -> int:
    """Compatibilidade com documentos livres já existentes; a interface nova usa criar_ordem_servico_sst."""
    _exigir_operacao(actor)
    tipo = _texto(tipo, 80, True); motivo = _texto(motivo, 80); titulo = _texto(titulo, 220, True)
    snapshot = conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False, sort_keys=True)
    if len(snapshot) > 200_000: raise RegraSSTError("Conteúdo do documento excede o limite permitido.")
    now = utcnow()
    with transacao() as conn:
        colaborador = _colaborador(conn, colaborador_id)
        if not colaborador or not colaborador["ativo"]: raise RegraSSTError("Colaborador indisponível.")
        numero = _novo_numero_documento(conn, now)
        result = conn.execute(insert(DOCUMENTOS_SST).values(numero=numero, colaborador_id=int(colaborador_id), entrega_id=None, tipo=tipo, motivo=motivo, titulo=titulo, conteudo_snapshot=snapshot, hash_documento=None, pdf_arquivo=None, nome_arquivo=None, status="Rascunho", criado_por=actor["usuario"], criado_em=now, fechado_em=None))
        documento_id = int(result.inserted_primary_key[0])
        registrar_auditoria(conn, actor["usuario"], "SST_DOCUMENTO_CRIADO", "sst_documento", numero, f"tipo={tipo};motivo={motivo or ''}")
        return documento_id


def obter_documento(documento_id: int) -> dict:
    stmt = select(
        DOCUMENTOS_SST,
        COLABORADORES.c.nome.label("colaborador"), COLABORADORES.c.matricula.label("matricula"), COLABORADORES.c.cpf.label("cpf"),
        COLABORADORES.c.funcao.label("funcao"), COLABORADORES.c.setor.label("setor"), COLABORADORES.c.data_admissao.label("data_admissao"),
        GHE.c.codigo.label("ghe_codigo"), GHE.c.nome.label("ghe_nome"),
    ).select_from(DOCUMENTOS_SST.join(COLABORADORES, DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id).outerjoin(GHE, COLABORADORES.c.ghe_id == GHE.c.id)).where(DOCUMENTOS_SST.c.id == int(documento_id))
    with transacao() as conn:
        row = conn.execute(stmt).mappings().first()
        if not row: raise RegraSSTError("Documento não encontrado.")
        return dict(row)


def fechar_documento_para_assinatura(actor: dict, documento_id: int, pdf_bytes: bytes, nome_arquivo: str) -> str:
    _exigir_operacao(actor)
    if not pdf_bytes:
        raise RegraSSTError("PDF do documento não foi informado.")
    if len(pdf_bytes) > STORAGE_LIMITE_BYTES:
        raise RegraSSTError("O PDF excede o limite de 10 MB.")
    nome_arquivo = _texto(nome_arquivo, 255, True)
    hash_documento = hashlib.sha256(pdf_bytes).hexdigest()

    with transacao() as conn:
        row = conn.execute(select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id))).mappings().first()
        if not row:
            raise RegraSSTError("Documento não encontrado.")
        if row["status"] != "Rascunho":
            raise RegraSSTError("Somente documentos em rascunho podem ser fechados.")
        numero = row["numero"]
        tipo = row["tipo"]

    storage_path = None
    if _usar_storage_sst():
        storage_path = _storage_path(numero, tipo, nome_arquivo)
        _storage_enviar(storage_path, pdf_bytes)

    try:
        with transacao() as conn:
            row = conn.execute(select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id))).mappings().first()
            if not row:
                raise RegraSSTError("Documento não encontrado.")
            if row["status"] != "Rascunho":
                raise RegraSSTError("Somente documentos em rascunho podem ser fechados.")
            valores = {
                "hash_documento": hash_documento,
                "nome_arquivo": nome_arquivo,
                "status": "Aguardando Assinatura",
                "fechado_em": utcnow(),
            }
            if storage_path:
                valores["storage_path"] = storage_path
                valores["pdf_arquivo"] = None
            else:
                valores["pdf_arquivo"] = pdf_bytes
            conn.execute(update(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id)).values(**valores))
            registrar_auditoria(
                conn, actor["usuario"], "SST_DOCUMENTO_FECHADO", "sst_documento", row["numero"],
                f"sha256={hash_documento};storage={'sim' if storage_path else 'nao'}"
            )
    except Exception:
        if storage_path:
            _storage_excluir(storage_path)
        raise
    return hash_documento


def obter_pdf_documento(documento_id: int) -> tuple[bytes, str, str]:
    with transacao() as conn:
        row = conn.execute(
            select(
                DOCUMENTOS_SST.c.pdf_arquivo, DOCUMENTOS_SST.c.storage_path,
                DOCUMENTOS_SST.c.nome_arquivo, DOCUMENTOS_SST.c.hash_documento
            ).where(DOCUMENTOS_SST.c.id == int(documento_id))
        ).mappings().first()
    if not row:
        raise RegraSSTError("Documento não encontrado.")

    if row.get("storage_path"):
        pdf = _storage_baixar(row["storage_path"])
    elif row.get("pdf_arquivo"):
        # Compatibilidade: documentos antigos continuam sendo lidos do PostgreSQL.
        pdf = bytes(row["pdf_arquivo"])
    else:
        raise RegraSSTError("Este documento ainda não possui PDF fechado.")

    hash_atual = hashlib.sha256(pdf).hexdigest()
    hash_esperado = row.get("hash_documento")
    if hash_esperado and hash_atual != hash_esperado:
        raise RegraSSTError("A integridade do PDF não confere com o hash registrado.")
    return pdf, row["nome_arquivo"], hash_esperado or hash_atual


def _limites_periodo(data_inicio: date | None, data_fim: date | None):
    inicio = fim = None
    if data_inicio:
        inicio = datetime.combine(data_inicio, time.min, TZ_BAHIA).astimezone(timezone.utc)
    if data_fim:
        fim = datetime.combine(data_fim + timedelta(days=1), time.min, TZ_BAHIA).astimezone(timezone.utc)
    return inicio, fim


def listar_documentos(limite: int = 100, colaborador_id: int | None = None, tipo: str | None = None,
                      status: str | None = None, data_inicio: date | None = None, data_fim: date | None = None,
                      busca: str | None = None) -> list[dict]:
    limite = max(1, min(int(limite), 500))
    stmt = select(
        DOCUMENTOS_SST.c.id, DOCUMENTOS_SST.c.numero, DOCUMENTOS_SST.c.tipo, DOCUMENTOS_SST.c.motivo,
        DOCUMENTOS_SST.c.titulo, DOCUMENTOS_SST.c.status, DOCUMENTOS_SST.c.criado_em, DOCUMENTOS_SST.c.fechado_em,
        DOCUMENTOS_SST.c.hash_documento, DOCUMENTOS_SST.c.storage_path, DOCUMENTOS_SST.c.nome_arquivo, DOCUMENTOS_SST.c.entrega_id,
        COLABORADORES.c.nome.label("colaborador"), COLABORADORES.c.matricula.label("matricula"),
    ).select_from(DOCUMENTOS_SST.join(COLABORADORES, DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id))
    cond = []
    if colaborador_id: cond.append(DOCUMENTOS_SST.c.colaborador_id == int(colaborador_id))
    if tipo and tipo != "Todos": cond.append(DOCUMENTOS_SST.c.tipo == tipo)
    if status and status != "Todos": cond.append(DOCUMENTOS_SST.c.status == status)
    inicio, fim = _limites_periodo(data_inicio, data_fim)
    if inicio: cond.append(DOCUMENTOS_SST.c.criado_em >= inicio)
    if fim: cond.append(DOCUMENTOS_SST.c.criado_em < fim)
    busca = _texto(busca, 120)
    if busca:
        termo = f"%{busca}%"
        cond.append(or_(
            DOCUMENTOS_SST.c.numero.ilike(termo),
            DOCUMENTOS_SST.c.titulo.ilike(termo),
            DOCUMENTOS_SST.c.motivo.ilike(termo),
            DOCUMENTOS_SST.c.tipo.ilike(termo),
            DOCUMENTOS_SST.c.status.ilike(termo),
            COLABORADORES.c.nome.ilike(termo),
            COLABORADORES.c.matricula.ilike(termo),
        ))
    if cond: stmt = stmt.where(and_(*cond))
    stmt = stmt.order_by(DOCUMENTOS_SST.c.criado_em.desc()).limit(limite)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


def listar_pendentes_assinatura(limite: int = 100) -> list[dict]:
    stmt = select(
        DOCUMENTOS_SST.c.id, DOCUMENTOS_SST.c.numero, DOCUMENTOS_SST.c.tipo, DOCUMENTOS_SST.c.titulo,
        DOCUMENTOS_SST.c.hash_documento, DOCUMENTOS_SST.c.fechado_em,
        COLABORADORES.c.nome.label("colaborador"), COLABORADORES.c.matricula.label("matricula"),
    ).select_from(DOCUMENTOS_SST.join(COLABORADORES, DOCUMENTOS_SST.c.colaborador_id == COLABORADORES.c.id)).where(DOCUMENTOS_SST.c.status == "Aguardando Assinatura").order_by(DOCUMENTOS_SST.c.fechado_em.desc()).limit(max(1, min(int(limite), 500)))
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


# ---------------------- ENTREGA EPI --------------------

def registrar_entrega_epi(actor: dict, colaborador_id: int, itens: Iterable[dict], motivo_entrega: str) -> int:
    _exigir_operacao(actor)
    itens = list(itens)
    if not itens: raise RegraSSTError("Inclua pelo menos um EPI na entrega.")
    if len(itens) > 5: raise RegraSSTError("Uma entrega pode conter no máximo 5 itens.")
    if motivo_entrega not in MOTIVOS_ENTREGA: raise RegraSSTError("Selecione um motivo de entrega válido.")
    ids = []
    for item in itens:
        epi_id = int(item.get("epi_id", 0))
        if epi_id in ids: raise RegraSSTError("O mesmo EPI foi selecionado mais de uma vez.")
        ids.append(epi_id)
    now = utcnow()
    storage_path_criado = None

    try:
        with transacao() as conn:
            _desativar_epis_ca_vencido(conn)
            colaborador = _colaborador(conn, colaborador_id)
            if not colaborador or not colaborador["ativo"]: raise RegraSSTError("Colaborador indisponível para entrega.")
            ghe = _ghe(conn, int(colaborador["ghe_id"])) if colaborador.get("ghe_id") else None
            preparados = []
            for item in itens:
                epi_id = int(item.get("epi_id", 0)); quantidade = int(item.get("quantidade", 0))
                if quantidade <= 0 or quantidade > 1000: raise RegraSSTError("Quantidade de EPI inválida.")
                epi = _epi(conn, epi_id)
                if not epi or not epi["ativo"]: raise RegraSSTError("Um dos EPIs está indisponível ou possui CA vencido.")
                if epi["validade_ca"] is None: raise RegraSSTError("Um dos EPIs não possui validade de CA informada.")
                if epi["validade_ca"] < _hoje_bahia(): raise RegraSSTError("Não é permitido entregar EPI com CA vencido.")
                preparados.append((dict(epi), quantidade))

            result = conn.execute(insert(ENTREGAS_EPI).values(colaborador_id=int(colaborador_id), responsavel_usuario=actor["usuario"], entregue_em=now, motivo_entrega=motivo_entrega, observacao=None, status="Registrada", criado_em=now))
            entrega_id = int(result.inserted_primary_key[0])
            itens_snapshot = []
            for epi, quantidade in preparados:
                conn.execute(insert(ITENS_ENTREGA_EPI).values(entrega_id=entrega_id, epi_id=int(epi["id"]), quantidade=quantidade, ca_no_momento=epi["ca"], validade_ca_no_momento=epi["validade_ca"]))
                itens_snapshot.append({"epi_id": int(epi["id"]), "nome": epi["nome"], "ca": epi["ca"], "validade_ca": epi["validade_ca"].isoformat(), "unidade": epi["unidade"], "quantidade": quantidade})

            numero = _novo_numero_documento(conn, now)
            snapshot_obj = {
                "modelo": "entrega_epi", "entrega_id": entrega_id,
                "colaborador": _snapshot_colaborador(dict(colaborador), dict(ghe) if ghe else None),
                "itens": itens_snapshot, "motivo_entrega": motivo_entrega,
                "responsavel_usuario": actor["usuario"], "entregue_em": now.isoformat(),
            }
            snapshot_json = json.dumps(snapshot_obj, ensure_ascii=False, sort_keys=True)
            titulo = f"Comprovante de Entrega de EPI #{entrega_id}"
            doc_result = conn.execute(insert(DOCUMENTOS_SST).values(
                numero=numero, colaborador_id=int(colaborador_id), entrega_id=entrega_id, tipo="Entrega de EPI", motivo=motivo_entrega,
                titulo=titulo, conteudo_snapshot=snapshot_json, hash_documento=None, pdf_arquivo=None, storage_path=None, nome_arquivo=None,
                status="Rascunho", criado_por=actor["usuario"], criado_em=now, fechado_em=None,
            ))
            documento_id = int(doc_result.inserted_primary_key[0])

            # Gera e fecha automaticamente o comprovante da entrega, sem etapa manual.
            from sst_reports import gerar_pdf_documento
            documento_pdf = {
                "id": documento_id, "numero": numero, "tipo": "Entrega de EPI", "motivo": motivo_entrega, "titulo": titulo,
                "conteudo_snapshot": snapshot_json, "criado_em": now,
                "colaborador": colaborador["nome"], "matricula": colaborador.get("matricula"), "cpf": colaborador.get("cpf"),
                "funcao": colaborador.get("funcao"), "setor": colaborador.get("setor"), "data_admissao": colaborador.get("data_admissao"),
                "ghe_codigo": ghe.get("codigo") if ghe else None, "ghe_nome": ghe.get("nome") if ghe else None,
            }
            pdf = gerar_pdf_documento(documento_pdf)
            if len(pdf) > STORAGE_LIMITE_BYTES:
                raise RegraSSTError("O PDF excede o limite de 10 MB.")
            hash_documento = hashlib.sha256(pdf).hexdigest()
            nome_arquivo = _nome_pdf(numero, "Entrega_de_EPI")

            valores_pdf = {
                "hash_documento": hash_documento, "nome_arquivo": nome_arquivo,
                "status": "Aguardando Assinatura", "fechado_em": utcnow(),
            }
            if _usar_storage_sst():
                storage_path_criado = _storage_path(numero, "Entrega de EPI", nome_arquivo)
                _storage_enviar(storage_path_criado, pdf)
                valores_pdf["storage_path"] = storage_path_criado
                valores_pdf["pdf_arquivo"] = None
            else:
                valores_pdf["pdf_arquivo"] = pdf

            conn.execute(update(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == documento_id).values(**valores_pdf))
            registrar_auditoria(conn, actor["usuario"], "SST_EPI_ENTREGUE", "sst_entrega_epi", str(entrega_id), f"colaborador_id={colaborador_id};itens={len(preparados)};motivo={motivo_entrega};documento={numero}")
            registrar_auditoria(conn, actor["usuario"], "SST_DOCUMENTO_FECHADO", "sst_documento", numero, f"sha256={hash_documento};geracao=automatica_entrega_epi;storage={'sim' if storage_path_criado else 'nao'}")
            return entrega_id
    except Exception:
        if storage_path_criado:
            _storage_excluir(storage_path_criado)
        raise


def listar_entregas(limite: int = 100) -> list[dict]:
    limite = max(1, min(int(limite), 500))
    stmt = select(
        ENTREGAS_EPI.c.id.label("entrega_id"), ENTREGAS_EPI.c.entregue_em, ENTREGAS_EPI.c.motivo_entrega,
        ENTREGAS_EPI.c.responsavel_usuario, COLABORADORES.c.nome.label("colaborador"), COLABORADORES.c.matricula.label("matricula"),
        EPIS.c.nome.label("epi"), ITENS_ENTREGA_EPI.c.ca_no_momento.label("ca"), ITENS_ENTREGA_EPI.c.validade_ca_no_momento.label("validade_ca"), ITENS_ENTREGA_EPI.c.quantidade,
    ).select_from(ENTREGAS_EPI.join(COLABORADORES, ENTREGAS_EPI.c.colaborador_id == COLABORADORES.c.id).join(ITENS_ENTREGA_EPI, ITENS_ENTREGA_EPI.c.entrega_id == ENTREGAS_EPI.c.id).join(EPIS, ITENS_ENTREGA_EPI.c.epi_id == EPIS.c.id)).order_by(ENTREGAS_EPI.c.entregue_em.desc(), ITENS_ENTREGA_EPI.c.id.asc()).limit(limite)
    with transacao() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]


# ---------------------- BIOMETRIA -----------------------

BIOMETRIA_MODELO_OFICIAL = "Nitgen Hamster DX HFDU06"
BIOMETRIA_JANELA_EVENTO_SEGUNDOS = 180


def _segredo_agente_biometrico() -> str:
    """Segredo compartilhado apenas entre o backend e o agente Windows local."""
    valor = os.getenv("SST_BIOMETRIC_AGENT_SECRET")
    if valor:
        return valor.strip()
    try:
        import streamlit as st
        valor = st.secrets.get("SST_BIOMETRIC_AGENT_SECRET")
        if valor:
            return str(valor).strip()
    except Exception:
        pass
    raise RegraSSTError(
        "O agente biométrico ainda não foi configurado. "
        "A assinatura permanece bloqueada até a instalação do leitor e do agente local."
    )


def _texto_evidencia(valor, limite: int, obrigatorio: bool = True) -> str | None:
    if valor is None:
        if obrigatorio:
            raise RegraSSTError("Evidência biométrica incompleta.")
        return None
    texto = str(valor).strip()
    if not texto:
        if obrigatorio:
            raise RegraSSTError("Evidência biométrica incompleta.")
        return None
    if len(texto) > limite:
        raise RegraSSTError("Evidência biométrica inválida.")
    return texto


def _timestamp_evidencia(valor: str) -> datetime:
    try:
        texto = str(valor).strip().replace("Z", "+00:00")
        momento = datetime.fromisoformat(texto)
        if momento.tzinfo is None:
            raise ValueError
        return momento.astimezone(timezone.utc)
    except Exception as exc:
        raise RegraSSTError("Data/hora da evidência biométrica é inválida.") from exc


def _payload_assinado(evidencia: dict) -> bytes:
    """Serialização que o agente Windows deverá usar antes de gerar o HMAC-SHA256."""
    payload = {k: v for k, v in evidencia.items() if k != "assinatura_hmac"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validar_evidencia_agente(evidencia: dict, tipo_evento: str) -> dict:
    """
    Valida a prova enviada pelo agente local.

    O Streamlit NÃO cria esta assinatura HMAC. Ela deverá ser produzida pelo agente
    Windows depois que o SDK Nitgen confirmar uma captura/correspondência real.
    """
    if not isinstance(evidencia, dict):
        raise RegraSSTError("Evidência biométrica inválida.")

    assinatura = _texto_evidencia(evidencia.get("assinatura_hmac"), 128)
    evento_id = _texto_evidencia(evidencia.get("evento_id"), 120)
    tipo = _texto_evidencia(evidencia.get("tipo_evento"), 40)
    if tipo != tipo_evento:
        raise RegraSSTError("Tipo de evento biométrico inválido.")

    momento = _timestamp_evidencia(_texto_evidencia(evidencia.get("timestamp"), 80))
    diferenca = abs((datetime.now(timezone.utc) - momento).total_seconds())
    if diferenca > BIOMETRIA_JANELA_EVENTO_SEGUNDOS:
        raise RegraSSTError("A evidência biométrica expirou. Faça uma nova leitura.")

    segredo = _segredo_agente_biometrico().encode("utf-8")
    esperado = hmac.new(segredo, _payload_assinado(evidencia), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura.lower(), esperado.lower()):
        raise RegraSSTError("A evidência não foi autenticada pelo agente biométrico autorizado.")

    return {
        "evento_id": evento_id,
        "timestamp": momento,
        "agente_id": _texto_evidencia(evidencia.get("agente_id"), 120),
        "estacao": _texto_evidencia(evidencia.get("estacao"), 160),
        "dispositivo_modelo": _texto_evidencia(evidencia.get("dispositivo_modelo"), 120),
        "dispositivo_serial": _texto_evidencia(evidencia.get("dispositivo_serial"), 120, False),
        "sdk_versao": _texto_evidencia(evidencia.get("sdk_versao"), 80, False),
        "referencia_biometrica": _texto_evidencia(evidencia.get("referencia_biometrica"), 255),
        "template_hash": _texto_evidencia(evidencia.get("template_hash"), 64, False),
        "resultado": _texto_evidencia(evidencia.get("resultado"), 40),
        "score_verificacao": int(evidencia.get("score_verificacao")) if evidencia.get("score_verificacao") is not None else None,
    }


def obter_biometria_colaborador(colaborador_id: int) -> dict | None:
    stmt = select(BIOMETRIAS_COLABORADORES).where(
        BIOMETRIAS_COLABORADORES.c.colaborador_id == int(colaborador_id)
    )
    with transacao() as conn:
        row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


def colaborador_possui_biometria(colaborador_id: int) -> bool:
    registro = obter_biometria_colaborador(colaborador_id)
    return bool(registro and registro.get("ativo"))


def registrar_cadastro_biometrico(actor: dict, colaborador_id: int, evidencia: dict) -> int:
    """
    Grava somente a REFERÊNCIA do template criado pelo agente Nitgen.
    A imagem da digital e o template biométrico bruto não são armazenados aqui.
    """
    _exigir_operacao(actor)
    ev = _validar_evidencia_agente(evidencia, "cadastro")
    if ev["resultado"] != "CADASTRADO":
        raise RegraSSTError("O agente não confirmou o cadastro biométrico.")
    if ev["dispositivo_modelo"] != BIOMETRIA_MODELO_OFICIAL:
        raise RegraSSTError("O evento foi produzido por um modelo de leitor não autorizado para esta estação.")
    if ev["template_hash"] and not re.fullmatch(r"[0-9a-fA-F]{64}", ev["template_hash"]):
        raise RegraSSTError("Hash do template biométrico inválido.")

    now = utcnow()
    with transacao() as conn:
        colab = _colaborador(conn, int(colaborador_id))
        if not colab or not colab.get("ativo"):
            raise RegraSSTError("Colaborador não encontrado ou inativo.")

        atual = conn.execute(
            select(BIOMETRIAS_COLABORADORES).where(
                BIOMETRIAS_COLABORADORES.c.colaborador_id == int(colaborador_id)
            )
        ).mappings().first()

        valores = dict(
            provedor="Nitgen eNBioBSP",
            referencia_biometrica=ev["referencia_biometrica"],
            template_hash=ev["template_hash"],
            agente_id=ev["agente_id"],
            dispositivo_modelo=ev["dispositivo_modelo"],
            dispositivo_serial=ev["dispositivo_serial"],
            sdk_versao=ev["sdk_versao"],
            ativo=True,
            atualizado_em=now,
        )
        if atual:
            conn.execute(
                update(BIOMETRIAS_COLABORADORES)
                .where(BIOMETRIAS_COLABORADORES.c.id == int(atual["id"]))
                .values(**valores)
            )
            biometria_id = int(atual["id"])
        else:
            valores["colaborador_id"] = int(colaborador_id)
            valores["cadastrado_em"] = now
            result = conn.execute(insert(BIOMETRIAS_COLABORADORES).values(**valores))
            biometria_id = int(result.inserted_primary_key[0])

        registrar_auditoria(
            conn, actor["usuario"], "SST_BIOMETRIA_CADASTRADA", "sst_colaborador", str(colaborador_id),
            f"biometria_id={biometria_id};agente={ev['agente_id']};dispositivo={ev['dispositivo_modelo']};evento={ev['evento_id']}"
        )
        return biometria_id


def registrar_assinatura_biometrica(actor: dict, documento_id: int, colaborador_id: int, evidencia: dict) -> int:
    """
    Marca um documento como Assinado SOMENTE após validar uma evidência HMAC
    produzida pelo agente local depois de uma correspondência biométrica real.
    """
    _exigir_operacao(actor)
    ev = _validar_evidencia_agente(evidencia, "verificacao")
    if ev["resultado"] != "VALIDADO":
        raise RegraSSTError("A impressão digital não foi validada pelo agente biométrico.")
    if ev["dispositivo_modelo"] != BIOMETRIA_MODELO_OFICIAL:
        raise RegraSSTError("O evento foi produzido por um modelo de leitor não autorizado para esta estação.")

    try:
        documento_evento = int(evidencia.get("documento_id"))
        colaborador_evento = int(evidencia.get("colaborador_id"))
    except Exception as exc:
        raise RegraSSTError("Documento ou colaborador ausente na evidência biométrica.") from exc
    hash_evento = _texto_evidencia(evidencia.get("hash_documento"), 64)

    if documento_evento != int(documento_id) or colaborador_evento != int(colaborador_id):
        raise RegraSSTError("A evidência biométrica não corresponde a esta solicitação de assinatura.")

    with transacao() as conn:
        doc = conn.execute(
            select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.id == int(documento_id))
        ).mappings().first()
        if not doc:
            raise RegraSSTError("Documento não encontrado.")
        if doc["status"] != "Aguardando Assinatura" or not doc["hash_documento"]:
            raise RegraSSTError("Documento não está disponível para assinatura.")
        if int(doc["colaborador_id"]) != int(colaborador_id):
            raise RegraSSTError("O colaborador informado não corresponde ao documento.")
        if not hmac.compare_digest(str(doc["hash_documento"]).lower(), hash_evento.lower()):
            raise RegraSSTError("O hash do documento não corresponde à evidência biométrica.")

        cadastro = conn.execute(
            select(BIOMETRIAS_COLABORADORES).where(
                and_(
                    BIOMETRIAS_COLABORADORES.c.colaborador_id == int(colaborador_id),
                    BIOMETRIAS_COLABORADORES.c.ativo.is_(True),
                )
            )
        ).mappings().first()
        if not cadastro:
            raise RegraSSTError("Este colaborador ainda não possui biometria cadastrada.")
        if not hmac.compare_digest(
            str(cadastro["referencia_biometrica"]), str(ev["referencia_biometrica"])
        ):
            raise RegraSSTError("A biometria validada não corresponde ao cadastro do colaborador.")

        evento_existente = conn.execute(
            select(ASSINATURAS_SST.c.id).where(ASSINATURAS_SST.c.evento_id == ev["evento_id"])
        ).first()
        if evento_existente:
            raise RegraSSTError("Este evento biométrico já foi utilizado.")

        result = conn.execute(insert(ASSINATURAS_SST).values(
            documento_id=int(documento_id),
            colaborador_id=int(colaborador_id),
            metodo="Biometria",
            status="Validada",
            hash_documento=doc["hash_documento"],
            assinado_em=utcnow(),
            estacao=ev["estacao"],
            referencia_biometrica=ev["referencia_biometrica"],
            agente_id=ev["agente_id"],
            dispositivo_modelo=ev["dispositivo_modelo"],
            dispositivo_serial=ev["dispositivo_serial"],
            sdk_versao=ev["sdk_versao"],
            evento_id=ev["evento_id"],
            score_verificacao=ev["score_verificacao"],
            detalhes=json.dumps({
                "resultado": ev["resultado"],
                "timestamp_agente": ev["timestamp"].isoformat(),
                "modelo_oficial": BIOMETRIA_MODELO_OFICIAL,
            }, ensure_ascii=False, sort_keys=True),
        ))
        assinatura_id = int(result.inserted_primary_key[0])

        conn.execute(
            update(DOCUMENTOS_SST)
            .where(DOCUMENTOS_SST.c.id == int(documento_id))
            .values(status="Assinado")
        )
        registrar_auditoria(
            conn, actor["usuario"], "SST_DOCUMENTO_ASSINADO_BIOMETRIA", "sst_documento", doc["numero"],
            f"assinatura_id={assinatura_id};sha256={doc['hash_documento']};evento={ev['evento_id']};agente={ev['agente_id']};score={ev['score_verificacao']}"
        )
        return assinatura_id
