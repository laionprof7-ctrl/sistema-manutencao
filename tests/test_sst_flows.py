from datetime import timedelta

import pytest
from sqlalchemy import delete, insert, select

from database import AUDITORIA, CHAMADOS, USUARIOS, transacao, utcnow
from security import hash_senha
from sst_database import (
    ASSINATURAS_SST, BIOMETRIAS_COLABORADORES, COLABORADORES,
    CONTADORES_SST, DOCUMENTOS_SST, ENTREGAS_EPI, EPIS, GHE,
    GHE_VINCULOS, ITENS_ENTREGA_EPI, inicializar_banco_sst,
)
from sst_services import (
    RegraSSTError, _hoje_bahia, cadastrar_colaborador, cadastrar_epi,
    cadastrar_ghe, registrar_entrega_epi,
)
from sst_fast_init import SCHEMA_VERSION, SCHEMA_VERSION_KEY, _marcar_schema_atualizado

ADMIN = {"usuario": "admin", "nome": "Admin Teste", "nivel": 4.0}


@pytest.fixture(autouse=True)
def banco_sst_limpo():
    inicializar_banco_sst()
    with transacao() as conn:
        for tabela in (
            ASSINATURAS_SST, BIOMETRIAS_COLABORADORES, DOCUMENTOS_SST,
            ITENS_ENTREGA_EPI, ENTREGAS_EPI, COLABORADORES, GHE_VINCULOS,
            GHE, EPIS, CONTADORES_SST, CHAMADOS, AUDITORIA, USUARIOS,
        ):
            conn.execute(delete(tabela))
        agora = utcnow()
        conn.execute(insert(USUARIOS).values(
            usuario="admin", senha=hash_senha("SenhaAdmin123"), nome="Admin Teste",
            nivel=4.0, ativo=True, criado_em=agora, atualizado_em=agora,
        ))


def _estrutura_basica():
    ghe_id = cadastrar_ghe(
        ADMIN, "GHE-01", "Operação", "Operacional", "Motorista",
        riscos="Ruído", medidas_preventivas="Usar EPI",
    )
    colaborador_id = cadastrar_colaborador(
        ADMIN, "Colaborador Teste", "Motorista", matricula="MAT-01",
        setor="Operacional", ghe_id=ghe_id,
    )
    epi_id = cadastrar_epi(
        ADMIN, "Protetor auricular", "CA-123", fabricante="Teste",
        validade_ca=_hoje_bahia() + timedelta(days=365),
    )
    return colaborador_id, epi_id


def test_entrega_epi_e_documento_sao_gravados_na_mesma_operacao():
    colaborador_id, epi_id = _estrutura_basica()
    entrega_id = registrar_entrega_epi(
        ADMIN, colaborador_id, [{"epi_id": epi_id, "quantidade": 2}],
        "Primeira entrega",
    )

    with transacao() as conn:
        entrega = conn.execute(select(ENTREGAS_EPI).where(ENTREGAS_EPI.c.id == entrega_id)).mappings().one()
        item = conn.execute(select(ITENS_ENTREGA_EPI).where(ITENS_ENTREGA_EPI.c.entrega_id == entrega_id)).mappings().one()
        documento = conn.execute(select(DOCUMENTOS_SST).where(DOCUMENTOS_SST.c.entrega_id == entrega_id)).mappings().one()

    assert entrega["status"] == "Registrada"
    assert item["quantidade"] == 2
    assert documento["status"] == "Aguardando Assinatura"
    assert documento["hash_documento"]
    assert bytes(documento["pdf_arquivo"]).startswith(b"%PDF-")


def test_entrega_rejeita_quantidade_invalida_sem_gravar_dados():
    colaborador_id, epi_id = _estrutura_basica()
    with pytest.raises(RegraSSTError, match="Quantidade"):
        registrar_entrega_epi(
            ADMIN, colaborador_id, [{"epi_id": epi_id, "quantidade": 0}],
            "Primeira entrega",
        )
    with transacao() as conn:
        assert conn.execute(select(ENTREGAS_EPI.c.id)).first() is None
        assert conn.execute(select(DOCUMENTOS_SST.c.id)).first() is None


def test_marcador_de_schema_pode_ser_atualizado_repetidamente():
    _marcar_schema_atualizado()
    _marcar_schema_atualizado()

    with transacao() as conn:
        versao = conn.execute(
            select(CONTADORES_SST.c.valor).where(
                CONTADORES_SST.c.chave == SCHEMA_VERSION_KEY
            )
        ).scalar_one()

    assert versao == SCHEMA_VERSION
