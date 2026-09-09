import getpass
from sqlalchemy import insert, select

from database import USUARIOS, inicializar_banco, registrar_auditoria, transacao, utcnow
from security import hash_senha, normalizar_usuario, usuario_valido, validar_senha_forte


def main():
    inicializar_banco()
    nome = input("Nome completo do administrador: ").strip()
    usuario = normalizar_usuario(input("Login do administrador: "))
    senha = getpass.getpass("Senha forte: ")
    confirma = getpass.getpass("Repita a senha: ")
    if senha != confirma:
        raise SystemExit("As senhas não coincidem.")
    if len(nome.split()) < 2:
        raise SystemExit("Informe nome e sobrenome.")
    if not usuario_valido(usuario):
        raise SystemExit("Login inválido.")
    ok, msg = validar_senha_forte(senha)
    if not ok:
        raise SystemExit(msg)
    now = utcnow()
    with transacao() as conn:
        if conn.execute(select(USUARIOS.c.usuario).where(USUARIOS.c.usuario == usuario)).first():
            raise SystemExit("Esse usuário já existe.")
        conn.execute(insert(USUARIOS).values(usuario=usuario, senha=hash_senha(senha), nome=nome, nivel=4.0, ativo=True, criado_em=now, atualizado_em=now))
        registrar_auditoria(conn, usuario, "ADMIN_INICIAL_CRIADO", "usuario", usuario)
    print("Administrador criado com sucesso.")

if __name__ == "__main__":
    main()
