from datetime import timedelta

import pytest
from sqlalchemy import delete, insert, select, update

from database import (
    AUDITORIA,
    CHAMADOS,
    CONTADORES,
    USUARIOS,
    arquivar_chamados_expirados,
    inicializar_banco,
    transacao,
    utcnow,
)
from security import hash_senha
from services import (
    ConcorrenciaError,
    RegraNegocioError,
    aprovar_chamado,
    atualizar_oficina,
    criar_chamado,
    criar_usuario,
    excluir_chamado,
)


ADMIN = {"usuario": "admin", "nome": "Admin Teste", "nivel": 4.0}


@pytest.fixture(autouse=True)
def banco_limpo():
    inicializar_banco()
    with transacao() as conn:
        conn.execute(delete(AUDITORIA))
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


def test_fluxo_critico_da_os():
    id_os = criar_chamado(ADMIN, "Caminhão", "abc-1234", "Falha no freio")
    criado = _chamado(id_os)
    assert criado["status"] == "Aguardando Aprovação"
    assert criado["placa"] == "ABC-1234"

    aprovar_chamado(ADMIN, criado["id"], "Alta", criado["versao"])
    aprovado = _chamado(id_os)
    assert aprovado["status"] == "Aguardando Manutenção"

    atualizar_oficina(ADMIN, aprovado["id"], "Em Andamento", "Mecânico Teste", aprovado["versao"])
    andamento = _chamado(id_os)
    atualizar_oficina(ADMIN, andamento["id"], "Concluído", "ignorado", andamento["versao"])
    concluido = _chamado(id_os)
    assert concluido["status"] == "Concluído"
    assert concluido["data_liberacao"] is not None
    assert concluido["mecanico_responsavel"] == "Mecânico Teste"


def test_exclusao_rejeita_versao_desatualizada():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC", "Defeito válido")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Baixa", row["versao"])

    with pytest.raises(ConcorrenciaError):
        excluir_chamado(ADMIN, row["id"], row["versao"])

    assert _chamado(id_os)["excluido"] is False


def test_arquivamento_expirado_revalida_estado_atual():
    id_os = criar_chamado(ADMIN, "Caminhão", "ABC", "Defeito válido")
    row = _chamado(id_os)
    with transacao() as conn:
        conn.execute(update(CHAMADOS).where(CHAMADOS.c.id == row["id"]).values(
            criado_em=utcnow() - timedelta(days=8), aprovado_coordenador=True,
            status="Aguardando Manutenção",
        ))

    assert arquivar_chamados_expirados() == 0
    assert _chamado(id_os)["arquivado"] is False


def test_usuario_e_normalizado_antes_de_persistir():
    criar_usuario(ADMIN, "  Joao.Silva  ", "SenhaForte123", "João Silva", 1.0)
    with transacao() as conn:
        assert conn.execute(select(USUARIOS.c.usuario).where(USUARIOS.c.usuario == "joao.silva")).scalar_one() == "joao.silva"


@pytest.mark.parametrize("campo", ["nome", "mecanico"])
def test_campos_longos_sao_rejeitados_com_erro_de_negocio(campo):
    if campo == "nome":
        with pytest.raises(RegraNegocioError, match="tamanho"):
            criar_usuario(ADMIN, "usuario", "SenhaForte123", "Nome " + "x" * 160, 1.0)
        return

    id_os = criar_chamado(ADMIN, "Caminhão", "ABC", "Defeito válido")
    row = _chamado(id_os)
    aprovar_chamado(ADMIN, row["id"], "Média", row["versao"])
    aprovado = _chamado(id_os)
    with pytest.raises(RegraNegocioError, match="tamanho"):
        atualizar_oficina(ADMIN, aprovado["id"], "Em Andamento", "x" * 161, aprovado["versao"])
