from datetime import timedelta

import pytest
from sqlalchemy import delete, insert, select, update

from database import (
    AUDITORIA, CHAMADOS, CONTADORES, DOCUMENTOS_MANUTENCAO, USUARIOS,
    arquivar_chamados_expirados, inicializar_banco, transacao, utcnow,
)
from security import hash_senha
from manutencao_documentos import DocumentoManutencaoError, obter_pdf_documento
from services import (
    ConcorrenciaError, aprovar_chamado, atualizar_oficina,
    criar_chamado, criar_usuario, excluir_chamado,
)

ADMIN = {"usuario": "admin", "nome": "Admin Teste", "nivel": 4.0}


@pytest.fixture(autouse=True)
def banco_limpo():
    inicializar_banco()
    with transacao() as conn:
        conn.execute(delete(AUDITORIA))
        conn.execute(delete(DOCUMENTOS_MANUTENCAO))
        conn.execute(delete(CHAMADOS))
        conn.execute(delete(USUARIOS))
        conn.execute(update(CONTADORES).where(CONTADORES.c.chave == "os").values(valor=1000))
        agora = utcnow()
        conn.execute(insert(USUARIOS).values(
            usuario="admin", senha=hash_senha("SenhaAdmin123"), nome="Admin Teste",
            nivel=4.0, ativo=True, criado_em=agora, atualizado_em=agora,
        ))


def _chamado(id_os):
    with transacao() as conn:
        return conn.execute(select(CHAMADOS).where(CHAMADOS.c.id_os == id_os)).mappings().one()


def test_fluxo_completo_da_os():
    id_os = criar_chamado(ADMIN, "Caminhão", "abc-1234", "Falha no freio")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Alta", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Em Andamento", "Mecânico Teste", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Concluído", "ignorado", row["versao"])
    concluido = _chamado(id_os)
    assert concluido["status"] == "Concluído"
    assert concluido["data_liberacao"] is not None
    with transacao() as conn:
        documento = conn.execute(
            select(DOCUMENTOS_MANUTENCAO).where(
                DOCUMENTOS_MANUTENCAO.c.chamado_id == concluido["id"]
            )
        ).mappings().one()
    assert documento["versao_documento"] == 1
    assert documento["hash_documento"]
    assert bytes(documento["pdf_arquivo"]).startswith(b"%PDF-")
    pdf, nome, hash_documento = obter_pdf_documento(documento["id"])
    assert pdf.startswith(b"%PDF-")
    assert nome.endswith("_v1.pdf")
    assert hash_documento == documento["hash_documento"]


def test_reconclusao_preserva_documento_antigo_e_cria_nova_versao():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC-1234", "Falha no freio")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Alta", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Concluído", "Mecânico Teste", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Em Andamento", "Mecânico Teste", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Concluído", "Mecânico Teste", row["versao"])

    with transacao() as conn:
        documentos = conn.execute(
            select(DOCUMENTOS_MANUTENCAO)
            .where(DOCUMENTOS_MANUTENCAO.c.chamado_id == row["id"])
            .order_by(DOCUMENTOS_MANUTENCAO.c.versao_documento)
        ).mappings().all()

    assert [doc["versao_documento"] for doc in documentos] == [1, 2]
    assert documentos[0]["hash_documento"] != documentos[1]["hash_documento"]


def test_download_rejeita_documento_adulterado():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC-1234", "Falha no freio")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Alta", row["versao"])
    row = _chamado(id_os)
    atualizar_oficina(ADMIN, row["id"], "Concluído", "Mecânico Teste", row["versao"])

    with transacao() as conn:
        documento_id = conn.execute(
            select(DOCUMENTOS_MANUTENCAO.c.id).where(
                DOCUMENTOS_MANUTENCAO.c.chamado_id == row["id"]
            )
        ).scalar_one()
        conn.execute(
            update(DOCUMENTOS_MANUTENCAO)
            .where(DOCUMENTOS_MANUTENCAO.c.id == documento_id)
            .values(pdf_arquivo=b"conteudo adulterado")
        )

    with pytest.raises(DocumentoManutencaoError, match="integridade"):
        obter_pdf_documento(documento_id)


def test_exclusao_rejeita_tela_desatualizada():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC", "Defeito válido")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Baixa", row["versao"])
    with pytest.raises(ConcorrenciaError):
        excluir_chamado(ADMIN, row["id"], row["versao"])
    assert _chamado(id_os)["excluido"] is False


def test_arquivamento_nao_atinge_os_aprovada():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC", "Defeito válido")
    row = _chamado(id_os)
    with transacao() as conn:
        conn.execute(update(CHAMADOS).where(CHAMADOS.c.id == row["id"]).values(
            criado_em=utcnow() - timedelta(days=8), aprovado_coordenador=True,
            status="Aguardando Manutenção",
        ))
    assert arquivar_chamados_expirados() == 0
    assert _chamado(id_os)["arquivado"] is False


def test_login_e_normalizado_antes_de_salvar():
    criar_usuario(ADMIN, "  Joao.Silva  ", "SenhaForte123", "João Silva", 1.0)
    with transacao() as conn:
        salvo = conn.execute(select(USUARIOS.c.usuario).where(USUARIOS.c.usuario == "joao.silva")).scalar_one()
    assert salvo == "joao.silva"
