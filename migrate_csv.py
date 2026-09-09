import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import insert, select, update

from config import FUSO_BR
from database import CHAMADOS, CONTADORES, USUARIOS, inicializar_banco, registrar_auditoria, transacao, utcnow


def parse_data(valor):
    if valor is None or str(valor).strip() in {"", "nan", "None"}:
        return None
    texto = str(valor).strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(texto, fmt)
            return dt.replace(tzinfo=FUSO_BR).astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def bool_sim(valor):
    return str(valor).strip().lower() in {"sim", "true", "1", "yes"}


def os_numero(id_os):
    m = re.fullmatch(r"OS-(\d+)", str(id_os).strip(), flags=re.I)
    return int(m.group(1)) if m else None


def migrar(usuarios_csv: Path, chamados_csv: Path):
    inicializar_banco()
    usuarios = pd.read_csv(usuarios_csv) if usuarios_csv.exists() else pd.DataFrame()
    chamados = pd.read_csv(chamados_csv) if chamados_csv.exists() else pd.DataFrame()

    with transacao() as conn:
        for _, r in usuarios.iterrows():
            usuario = str(r.get("usuario", "")).strip().lower()
            if not usuario:
                continue
            existe = conn.execute(select(USUARIOS.c.usuario).where(USUARIOS.c.usuario == usuario)).first()
            if existe:
                continue
            now = utcnow()
            conn.execute(insert(USUARIOS).values(
                usuario=usuario,
                senha=str(r.get("senha", "")),
                nome=str(r.get("nome", usuario)).strip() or usuario,
                nivel=float(r.get("nivel", 1.0)),
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            ))

        maior_os = 1000
        for _, r in chamados.iterrows():
            id_os = str(r.get("ID_OS", "")).strip()
            n = os_numero(id_os)
            if n:
                maior_os = max(maior_os, n)
            if id_os and conn.execute(select(CHAMADOS.c.id).where(CHAMADOS.c.id_os == id_os)).first():
                continue
            criado = parse_data(r.get("Data")) or utcnow()
            aprovacao = parse_data(r.get("Data_Aprovacao"))
            liberacao = parse_data(r.get("Data_Liberacao"))
            conn.execute(insert(CHAMADOS).values(
                id_os=id_os or None,
                criado_em=criado,
                solicitante_usuario=None,
                motorista=str(r.get("Motorista", "Não Identificado")),
                veiculo=str(r.get("Veiculo", "Não Informado")),
                placa=str(r.get("Placa", "")).upper(),
                descricao_problema=str(r.get("Descricao_Problema", "Sem descrição")),
                status=str(r.get("Status", "Aguardando Aprovação")),
                prioridade=str(r.get("Prioridade", "Pendente")),
                aprovado_coordenador=bool_sim(r.get("Aprovado_Coordenador")),
                aprovado_por=None,
                data_aprovacao=aprovacao,
                mecanico_responsavel=None if str(r.get("Mecanico_Responsavel", "")).strip() in {"", "Não Atribuído", "nan"} else str(r.get("Mecanico_Responsavel")).strip(),
                data_liberacao=liberacao,
                arquivado=bool_sim(r.get("Arquivado")),
                excluido=False,
                excluido_em=None,
                excluido_por=None,
                versao=1,
                atualizado_em=utcnow(),
            ))
        atual = conn.execute(select(CONTADORES.c.valor).where(CONTADORES.c.chave == "os")).scalar_one()
        if maior_os > atual:
            conn.execute(update(CONTADORES).where(CONTADORES.c.chave == "os").values(valor=maior_os))
        registrar_auditoria(conn, "migracao", "MIGRACAO_CSV", "sistema", None, f"usuarios={len(usuarios)};chamados={len(chamados)}")

    print("Migração concluída.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--usuarios", default="usuarios.csv")
    parser.add_argument("--chamados", default="chamados_manutencao.csv")
    args = parser.parse_args()
    migrar(Path(args.usuarios), Path(args.chamados))

if __name__ == "__main__":
    main()
