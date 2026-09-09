from __future__ import annotations

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from database import AUDITORIA, CHAMADOS, CONTADORES, USUARIOS, registrar_auditoria, transacao, utcnow
from permissions import pode_conceder_nivel, pode_editar_usuario, pode_gerir_os, pode_gerir_usuarios, pode_triagem, pode_ver_oficina
from security import hash_senha, usuario_valido, validar_senha_forte

class RegraNegocioError(ValueError):
    pass

class ConcorrenciaError(RuntimeError):
    pass


def _usuario(conn, usuario: str):
    return conn.execute(select(USUARIOS).where(USUARIOS.c.usuario == usuario)).mappings().first()


def criar_usuario(actor: dict, usuario: str, senha: str, nome: str, nivel: float) -> None:
    if not pode_gerir_usuarios(float(actor["nivel"])):
        raise RegraNegocioError("Sem permissão para criar usuários.")
    if not pode_conceder_nivel(float(actor["nivel"]), float(nivel)):
        raise RegraNegocioError("Você não pode conceder esse nível de acesso.")
    if not usuario_valido(usuario):
        raise RegraNegocioError("Login inválido. Use 3–40 caracteres: letras, números, ponto, _ ou -.")
    partes = [p for p in nome.strip().split() if p]
    if len(partes) < 2:
        raise RegraNegocioError("Digite nome e sobrenome.")
    ok, msg = validar_senha_forte(senha)
    if not ok:
        raise RegraNegocioError(msg)
    now = utcnow()
    try:
        with transacao() as conn:
            conn.execute(insert(USUARIOS).values(
                usuario=usuario, senha=hash_senha(senha), nome=" ".join(partes), nivel=float(nivel),
                ativo=True, criado_em=now, atualizado_em=now
            ))
            registrar_auditoria(conn, actor["usuario"], "USUARIO_CRIADO", "usuario", usuario, f"nivel={nivel:g}")
    except IntegrityError as exc:
        raise RegraNegocioError("Esse usuário já existe.") from exc


def alterar_nome(actor: dict, alvo: str, novo_nome: str) -> None:
    partes = [p for p in novo_nome.strip().split() if p]
    if len(partes) < 2:
        raise RegraNegocioError("Digite nome e sobrenome.")
    with transacao() as conn:
        row = _usuario(conn, alvo)
        if not row:
            raise RegraNegocioError("Usuário não encontrado.")
        if alvo != actor["usuario"] and not pode_editar_usuario(float(actor["nivel"]), float(row["nivel"])):
            raise RegraNegocioError("Sem permissão para editar esse usuário.")
        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == alvo).values(nome=" ".join(partes), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "USUARIO_NOME_ALTERADO", "usuario", alvo)


def alterar_nivel(actor: dict, alvo: str, novo_nivel: float) -> None:
    if alvo == actor["usuario"]:
        raise RegraNegocioError("Você não pode alterar o próprio nível.")
    with transacao() as conn:
        row = _usuario(conn, alvo)
        if not row or not pode_editar_usuario(float(actor["nivel"]), float(row["nivel"])):
            raise RegraNegocioError("Sem permissão para alterar esse nível.")
        if not pode_conceder_nivel(float(actor["nivel"]), float(novo_nivel)):
            raise RegraNegocioError("Você não pode conceder esse nível.")
        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == alvo).values(nivel=float(novo_nivel), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "USUARIO_NIVEL_ALTERADO", "usuario", alvo, f"nivel={novo_nivel:g}")


def redefinir_senha(actor: dict, alvo: str, nova_senha: str) -> None:
    ok, msg = validar_senha_forte(nova_senha)
    if not ok:
        raise RegraNegocioError(msg)
    with transacao() as conn:
        row = _usuario(conn, alvo)
        if not row:
            raise RegraNegocioError("Usuário não encontrado.")
        if alvo != actor["usuario"] and not pode_editar_usuario(float(actor["nivel"]), float(row["nivel"])):
            raise RegraNegocioError("Sem permissão para redefinir essa senha.")
        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == alvo).values(senha=hash_senha(nova_senha), atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "USUARIO_SENHA_REDEFINIDA", "usuario", alvo)


def excluir_usuario(actor: dict, alvo: str) -> None:
    if alvo == actor["usuario"]:
        raise RegraNegocioError("Você não pode excluir sua própria conta.")
    with transacao() as conn:
        row = _usuario(conn, alvo)
        if not row or not pode_editar_usuario(float(actor["nivel"]), float(row["nivel"])):
            raise RegraNegocioError("Sem permissão para excluir esse usuário.")
        # Desativar preserva rastreabilidade e referências históricas.
        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == alvo).values(ativo=False, atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "USUARIO_DESATIVADO", "usuario", alvo)


def reativar_usuario(actor: dict, alvo: str) -> None:
    with transacao() as conn:
        row = _usuario(conn, alvo)
        if not row:
            raise RegraNegocioError("Usuário não encontrado.")
        if bool(row["ativo"]):
            raise RegraNegocioError("Essa conta já está ativa.")
        if not pode_editar_usuario(float(actor["nivel"]), float(row["nivel"])):
            raise RegraNegocioError("Sem permissão para reativar esse usuário.")
        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == alvo).values(ativo=True, atualizado_em=utcnow()))
        registrar_auditoria(conn, actor["usuario"], "USUARIO_REATIVADO", "usuario", alvo)


def criar_chamado(actor: dict, veiculo: str, placa: str, descricao: str) -> str:
    veiculo, placa, descricao = veiculo.strip(), placa.strip().upper(), descricao.strip()
    if not veiculo or not placa or len(descricao) < 5:
        raise RegraNegocioError("Preencha veículo, placa/identificação e uma descrição válida.")
    if len(placa) > 60 or len(descricao) > 2000 or len(veiculo) > 160:
        raise RegraNegocioError("Um dos campos excede o tamanho permitido.")
    now = utcnow()
    with transacao() as conn:
        contador = conn.execute(
            select(CONTADORES.c.valor).where(CONTADORES.c.chave == "os").with_for_update()
        ).scalar_one()
        proximo = int(contador) + 1
        conn.execute(update(CONTADORES).where(CONTADORES.c.chave == "os").values(valor=proximo))
        id_os = f"OS-{proximo}"
        conn.execute(insert(CHAMADOS).values(
            id_os=id_os, criado_em=now, solicitante_usuario=actor["usuario"], motorista=actor["nome"],
            veiculo=veiculo, placa=placa, descricao_problema=descricao,
            status="Aguardando Aprovação", prioridade="Pendente", aprovado_coordenador=False,
            aprovado_por=None, data_aprovacao=None, mecanico_responsavel=None,
            data_liberacao=None, arquivado=False, excluido=False, excluido_em=None, excluido_por=None, versao=1, atualizado_em=now,
        ))
        registrar_auditoria(conn, actor["usuario"], "OS_CRIADA", "chamado", id_os, f"placa={placa}")
        return id_os


def _chamado(conn, id_interno: int):
    return conn.execute(select(CHAMADOS).where(CHAMADOS.c.id == int(id_interno))).mappings().first()


def aprovar_chamado(actor: dict, id_interno: int, prioridade: str, versao: int) -> None:
    if not pode_triagem(float(actor["nivel"])):
        raise RegraNegocioError("Sem permissão para aprovar chamados.")
    if prioridade not in {"Alta", "Média", "Baixa"}:
        raise RegraNegocioError("Prioridade inválida.")
    with transacao() as conn:
        row = _chamado(conn, id_interno)
        if not row or row["arquivado"]:
            raise RegraNegocioError("Chamado indisponível.")
        if row["aprovado_coordenador"]:
            raise RegraNegocioError("Esse chamado já foi aprovado.")
        result = conn.execute(update(CHAMADOS).where(
            (CHAMADOS.c.id == id_interno) & (CHAMADOS.c.versao == int(versao))
        ).values(
            aprovado_coordenador=True, aprovado_por=actor["usuario"], prioridade=prioridade,
            status="Aguardando Manutenção", data_aprovacao=utcnow(), atualizado_em=utcnow(),
            versao=CHAMADOS.c.versao + 1
        ))
        if result.rowcount != 1:
            raise ConcorrenciaError("Esse chamado foi alterado por outra pessoa. Atualize a tela.")
        registrar_auditoria(conn, actor["usuario"], "OS_APROVADA", "chamado", row["id_os"], f"prioridade={prioridade}")


def atualizar_oficina(actor: dict, id_interno: int, novo_status: str, mecanico: str, versao: int) -> None:
    if not pode_ver_oficina(float(actor["nivel"])):
        raise RegraNegocioError("Sem permissão para alterar a oficina.")
    if novo_status not in {"Aguardando Manutenção", "Em Andamento", "Concluído"}:
        raise RegraNegocioError("Status inválido.")
    with transacao() as conn:
        row = _chamado(conn, id_interno)
        if not row or row["arquivado"] or not row["aprovado_coordenador"]:
            raise RegraNegocioError("Chamado indisponível para a oficina.")
        atual = (row["mecanico_responsavel"] or "").strip()
        informado = (mecanico or "").strip()
        if atual:
            informado = atual
        elif len(informado) < 3:
            raise RegraNegocioError("Informe o mecânico responsável.")
        liberacao = row["data_liberacao"]
        if novo_status == "Concluído" and liberacao is None:
            liberacao = utcnow()
        elif novo_status != "Concluído":
            liberacao = None
        result = conn.execute(update(CHAMADOS).where(
            (CHAMADOS.c.id == id_interno) & (CHAMADOS.c.versao == int(versao))
        ).values(
            status=novo_status, mecanico_responsavel=informado, data_liberacao=liberacao,
            atualizado_em=utcnow(), versao=CHAMADOS.c.versao + 1
        ))
        if result.rowcount != 1:
            raise ConcorrenciaError("Esse chamado foi alterado por outra pessoa. Atualize a tela.")
        registrar_auditoria(conn, actor["usuario"], "OS_OFICINA_ATUALIZADA", "chamado", row["id_os"], f"status={novo_status};mecanico={informado}")


def arquivar_chamado(actor: dict, id_interno: int, arquivar: bool, versao: int) -> None:
    if not pode_gerir_os(float(actor["nivel"])):
        raise RegraNegocioError("Sem permissão para arquivar chamados.")
    with transacao() as conn:
        row = _chamado(conn, id_interno)
        if not row:
            raise RegraNegocioError("Chamado não encontrado.")
        result = conn.execute(update(CHAMADOS).where(
            (CHAMADOS.c.id == id_interno) & (CHAMADOS.c.versao == int(versao))
        ).values(arquivado=bool(arquivar), atualizado_em=utcnow(), versao=CHAMADOS.c.versao + 1))
        if result.rowcount != 1:
            raise ConcorrenciaError("Esse chamado foi alterado por outra pessoa. Atualize a tela.")
        registrar_auditoria(conn, actor["usuario"], "OS_ARQUIVADA" if arquivar else "OS_DESARQUIVADA", "chamado", row["id_os"])


def excluir_chamado(actor: dict, id_interno: int) -> None:
    if not pode_gerir_os(float(actor["nivel"])):
        raise RegraNegocioError("Sem permissão para excluir chamados.")
    with transacao() as conn:
        row = _chamado(conn, id_interno)
        if not row:
            raise RegraNegocioError("Chamado não encontrado.")
        conn.execute(update(CHAMADOS).where(CHAMADOS.c.id == id_interno).values(excluido=True, excluido_em=utcnow(), excluido_por=actor["usuario"], atualizado_em=utcnow(), versao=CHAMADOS.c.versao + 1))
        registrar_auditoria(conn, actor["usuario"], "OS_EXCLUIDA_LOGICAMENTE", "chamado", row["id_os"], f"placa={row['placa']}")
