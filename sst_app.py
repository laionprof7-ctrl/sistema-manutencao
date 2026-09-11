import os
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from PIL import Image

from config import (
    ARQUIVO_LOGO, FUSO_BR, NIVEIS,
    PRIORIDADES, VEICULOS,
)
from database import (
    inicializar_banco, listar_auditoria, listar_chamados, listar_usuarios, resumo_chamados,
    obter_usuario, transacao, USUARIOS, utcnow,
)
from permissions import pode_editar_usuario, pode_gerir_os, pode_gerir_usuarios, pode_triagem, pode_ver_oficina
from reports import gerar_relatorio_pdf
from security import hash_senha, normalizar_usuario, verificar_senha
from services import (
    ConcorrenciaError, RegraNegocioError, alterar_nome, alterar_nivel, aprovar_chamado,
    alterar_propria_senha, arquivar_chamado, atualizar_oficina, criar_chamado, criar_usuario,
    excluir_chamado, excluir_usuario, reativar_usuario, redefinir_senha,
)
from sqlalchemy import update

# ---------- Aparência ----------
logo_img = None
if os.path.exists(ARQUIVO_LOGO):
    try:
        logo_img = Image.open(ARQUIVO_LOGO)
    except Exception:
        logo_img = None

st.set_page_config(
    page_title="Copa Ambiental - Manutenção",
    page_icon=logo_img if logo_img else "🚛",
    layout="wide",
)

st.markdown(
    """
    <style>
      #MainMenu, footer, header, [data-testid="stHeader"] {visibility:hidden; display:none;}
      .block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1500px;}
      div.stButton > button, div.stDownloadButton > button {width:100%; min-height:46px; font-weight:600; border-radius:10px;}
      div[data-testid="stMetric"] {border:1px solid #e8e8e8; padding:12px; border-radius:12px;}
      .small-muted {opacity:.72; font-size:.9rem;}
      @media (max-width: 768px) {
        .block-container {padding-left:.8rem; padding-right:.8rem; padding-top:.6rem;}
        h1 {font-size:2rem !important;}
        div.stButton > button, div.stDownloadButton > button {min-height:52px;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Cache / desempenho ----------
@st.cache_resource(show_spinner=False)
def preparar_banco():
    # create_all faz várias consultas de metadados no PostgreSQL.
    # Rodar uma vez por processo evita repetir isso em todo clique/rerun.
    inicializar_banco()
    return True


@st.cache_data(ttl=12, show_spinner=False)
def carregar_chamados():
    return listar_chamados()


@st.cache_data(ttl=12, show_spinner=False)
def carregar_usuarios():
    return listar_usuarios()


@st.cache_data(ttl=10, show_spinner=False)
def carregar_auditoria(limite: int = 500):
    return listar_auditoria(limite)


@st.cache_data(ttl=10, show_spinner=False)
def carregar_resumo():
    return resumo_chamados()


@st.cache_data(ttl=600, show_spinner=False)
def gerar_pdf_em_cache(df_rel: pd.DataFrame, subtitulo: str = "") -> bytes:
    return gerar_relatorio_pdf(df_rel, subtitulo)


def limpar_cache_dados():
    carregar_chamados.clear()
    carregar_usuarios.clear()
    carregar_auditoria.clear()
    carregar_resumo.clear()


preparar_banco()

# ---------- Sessão ----------
SESSION_DURATION_SECONDS = 60 * 60
SESSION_WARNING_SECONDS = 5 * 60


def _init_state():
    defaults = {
        "logged_in": False,
        "user_info": None,
        "aba_ativa": "Menu",
        "user_checked_at": 0.0,
        "session_expires_at": None,
        "session_warning_shown": False,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _iniciar_ou_renovar_sessao() -> None:
    st.session_state.session_expires_at = time.time() + SESSION_DURATION_SECONDS
    st.session_state.session_warning_shown = False


def _segundos_restantes_sessao() -> int:
    expira_em = st.session_state.get("session_expires_at")
    if not expira_em:
        return 0
    return max(0, int(float(expira_em) - time.time()))


def _formatar_tempo_sessao(segundos: int) -> str:
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def sair(mensagem: str | None = None):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.aba_ativa = "Menu"
    st.session_state.session_expires_at = None
    st.session_state.session_warning_shown = False
    if mensagem:
        st.session_state["logout_message"] = mensagem
    st.rerun()


def validar_sessao() -> None:
    if st.session_state.logged_in and _segundos_restantes_sessao() <= 0:
        sair("Sua sessão expirou. Entre novamente para continuar.")


@st.dialog("Sua sessão está terminando", dismissible=False)
def _popup_renovar_sessao() -> None:
    restante = _segundos_restantes_sessao()
    st.warning(
        f"Sua sessão expira em **{_formatar_tempo_sessao(restante)}**. "
        "Deseja continuar conectado?"
    )
    st.caption("Por segurança, a sessão não é renovada automaticamente pelo uso do sistema.")

    c1, c2 = st.columns(2)
    if c1.button("Renovar por mais 1 hora", type="primary", use_container_width=True, key="renovar_sessao_1h"):
        _iniciar_ou_renovar_sessao()
        st.rerun()
    if c2.button("Sair agora", use_container_width=True, key="encerrar_sessao_agora"):
        sair("Sessão encerrada com segurança.")


@st.fragment(run_every=1)
def _contador_sessao() -> None:
    if not st.session_state.logged_in:
        return

    restante = _segundos_restantes_sessao()
    if restante <= 0:
        sair("Sua sessão expirou. Entre novamente para continuar.")

    texto = _formatar_tempo_sessao(restante)
    if restante <= SESSION_WARNING_SECONDS:
        st.warning(f"⏱️ Sessão: {texto}")
        if not st.session_state.get("session_warning_shown", False):
            st.session_state.session_warning_shown = True
            _popup_renovar_sessao()
    else:
        st.caption(f"⏱️ Sessão: {texto}")


def recarregar_usuario_logado(forcar: bool = False):
    # Evita uma ida ao PostgreSQL em cada clique. Revalida periodicamente
    # e imediatamente quando uma ação administrativa exigir isso.
    agora = time.time()
    if not forcar and agora - float(st.session_state.get("user_checked_at", 0.0)) < 30:
        return
    atual = obter_usuario(st.session_state.user_info["usuario"]) if st.session_state.user_info else None
    if not atual or not bool(atual.get("ativo", True)):
        sair("Sua conta não está mais ativa.")
    st.session_state.user_info = atual
    st.session_state.user_checked_at = agora


def executar(acao, *args, sucesso: str | None = None, **kwargs):
    try:
        resultado = acao(*args, **kwargs)
        limpar_cache_dados()
        if sucesso:
            st.success(sucesso)
        return True, resultado
    except ConcorrenciaError as exc:
        st.warning(str(exc))
    except RegraNegocioError as exc:
        st.error(str(exc))
    except Exception:
        st.error("Ocorreu um erro inesperado. A operação não foi concluída.")
    return False, None


_init_state()
validar_sessao()

# ---------- Login ----------
if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.25, 1])
    with col:
        if logo_img:
            st.image(logo_img, width=280)
        st.subheader("Acesso ao Sistema")
        st.caption("Sistema interno de manutenção e ordens de serviço")
        mensagem_logout = st.session_state.pop("logout_message", None)
        if mensagem_logout:
            st.info(mensagem_logout)

        with st.form("login"):
            usuario = normalizar_usuario(st.text_input("Usuário"))
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

        if entrar:
            dados = obter_usuario(usuario)
            valido = False
            upgrade = False
            if dados and bool(dados.get("ativo", True)):
                valido, upgrade = verificar_senha(senha, dados["senha"])
            if valido:
                if upgrade:
                    with transacao() as conn:
                        conn.execute(update(USUARIOS).where(USUARIOS.c.usuario == usuario).values(senha=hash_senha(senha), atualizado_em=utcnow()))
                st.session_state.logged_in = True
                st.session_state.user_info = obter_usuario(usuario)
                st.session_state.aba_ativa = "Menu"
                st.session_state.user_checked_at = time.time()
                _iniciar_ou_renovar_sessao()
                st.rerun()
            st.error("Usuário ou senha incorretos.")
    st.stop()

# ---------- Usuário autenticado ----------
recarregar_usuario_logado()
user_data = st.session_state.user_info
nivel_user = float(user_data["nivel"])
usuario_atual = str(user_data["usuario"])


def navegar(destino: str):
    st.session_state.aba_ativa = destino


def logout_callback():
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.aba_ativa = "Menu"
    st.session_state.session_expires_at = None
    st.session_state.session_warning_shown = False

if logo_img:
    st.sidebar.image(logo_img, use_container_width=True)
st.sidebar.write(f"👤 **{user_data['nome']}**")
st.sidebar.caption(f"{NIVEIS.get(nivel_user, 'Nível')} · acesso {nivel_user:g}")
with st.sidebar:
    _contador_sessao()
st.sidebar.divider()
st.sidebar.button("🏠 Menu Principal", use_container_width=True, on_click=navegar, args=("Menu",))
st.sidebar.button("🚪 Sair", use_container_width=True, on_click=logout_callback)

aba = st.session_state.aba_ativa

# ---------- Menu ----------
if aba == "Menu":
    st.title("Menu Principal")
    st.caption(f"Bem-vindo, {user_data['nome']}")

    # Motoristas (nível 1) não precisam visualizar indicadores operacionais da gestão.
    if nivel_user != 1.0:
        @st.fragment(run_every=30)
        def painel_resumo():
            try:
                resumo = carregar_resumo()
            except Exception:
                resumo = {"pendentes": 0, "andamento": 0, "concluidos": 0}
            m1, m2, m3 = st.columns(3)
            m1.metric("Aguardando aprovação", resumo["pendentes"])
            m2.metric("Em andamento", resumo["andamento"])
            m3.metric("Concluídos · últimos 7 dias", resumo["concluidos"])
            st.caption("Indicadores atualizados automaticamente a cada 30 segundos.")

        painel_resumo()
        st.write("")
    opcoes = [("📝 Abrir Chamado", "Abrir Chamado"), ("🔍 Consultar Chamados", "Consultar Chamados")]
    if pode_ver_oficina(nivel_user): opcoes.append(("🛠️ Painel da Oficina", "Oficina"))
    if pode_triagem(nivel_user): opcoes.append(("🎯 Triagem e Prioridade", "Triagem"))
    if pode_gerir_usuarios(nivel_user):
        opcoes.append(("👤 Gestão de Usuários", "Usuarios"))
    else:
        opcoes.append(("🔑 Alterar minha senha", "Minha Senha"))
    if pode_gerir_os(nivel_user): opcoes.append(("🧾 Auditoria", "Auditoria"))

    # Navegação principal também fica no corpo da página para funcionar bem no celular,
    # onde a barra lateral do Streamlit pode ficar recolhida/oculta.
    opcoes.append(("🚪 Sair / Logout", "Logout"))

    cols = st.columns(2)
    for i, (rotulo, destino) in enumerate(opcoes):
        with cols[i % 2]:
            if destino == "Logout":
                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=logout_callback)
            else:
                st.button(rotulo, key=f"menu_{destino}", use_container_width=True, on_click=navegar, args=(destino,))
    st.stop()

st.button("← Voltar ao menu", on_click=navegar, args=("Menu",))

# ---------- Abrir chamado ----------
if aba == "Abrir Chamado":
    st.header("📝 Nova Ordem de Serviço")
    c1, c2 = st.columns([3, 1])
    with c1: veiculo_sel = st.selectbox("Veículo / Equipamento", VEICULOS)
    with c2:
        st.write(""); st.write("")
        outro = st.checkbox("Outros")
    outro_nome = st.text_input("Especifique o veículo/equipamento", max_chars=160) if outro else ""
    with st.form("novo_chamado", clear_on_submit=True):
        placa = st.text_input("Placa ou Identificação", max_chars=60)
        descricao = st.text_area("Descrição do Problema / Defeito", height=140, max_chars=2000)
        enviar = st.form_submit_button("Enviar Chamado", use_container_width=True)
    if enviar:
        ok, id_os = executar(criar_chamado, user_data, outro_nome if outro else veiculo_sel, placa, descricao)
        if ok: st.success(f"Chamado {id_os} enviado com sucesso.")
    st.stop()

# ---------- Consultar ----------
if aba == "Consultar Chamados":
    st.header("🔍 Consultar Ordens de Serviço")
    try:
        df_os = carregar_chamados()
    except Exception:
        st.error("Não foi possível carregar os chamados. Verifique a conexão com o banco.")
        st.stop()
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: busca = st.text_input("Buscar por placa, ID da OS ou veículo")
    with c2: exibir = st.selectbox("Exibir", ["Ativos", "Arquivados"])
    with c3: filtro_status = st.selectbox("Status", ["Todos", "Aguardando Aprovação", "Aguardando Manutenção", "Em Andamento", "Concluído"])
    df = df_os.copy()
    df = df[df["Arquivado"] == ("Sim" if exibir == "Arquivados" else "Não")]
    if busca.strip():
        q = busca.strip()
        df = df[
            df["Placa"].astype(str).str.contains(q, case=False, na=False)
            | df["ID_OS"].astype(str).str.contains(q, case=False, na=False)
            | df["Veiculo"].astype(str).str.contains(q, case=False, na=False)
        ]
    if filtro_status != "Todos": df = df[df["Status"] == filtro_status]

    if nivel_user == 1.0:
        vis = df[["ID_OS", "Data", "Veiculo", "Placa", "Descricao_Problema", "Status"]].copy()
        vis["Status"] = vis["Status"].replace({"Aguardando Aprovação": "Em Aberto", "Aguardando Manutenção": "Em Aberto"})
        vis.columns = ["Nº OS", "Data", "Veículo", "Placa", "Descrição", "Status"]
    else:
        vis = df[["ID_OS", "Data", "Motorista", "Veiculo", "Placa", "Descricao_Problema", "Status", "Prioridade", "Mecanico_Responsavel"]].copy()
        vis.columns = ["Nº OS", "Data", "Solicitante", "Veículo", "Placa", "Descrição", "Status", "Prioridade", "Mecânico"]
    st.dataframe(vis, use_container_width=True, hide_index=True)

    if pode_triagem(nivel_user) and not df.empty:
        with st.container(border=True):
            st.subheader("📥 Relatório individual")

            opcoes_relatorio = {
                f"{r.ID_OS} · {r.Veiculo} ({r.Placa})": r.id
                for r in df.itertuples()
            }

            rotulo_relatorio = st.selectbox(
                "Ordem de Serviço",
                list(opcoes_relatorio.keys()),
                key="relatorio_os_selecionada",
            )

            id_relatorio = opcoes_relatorio[rotulo_relatorio]
            df_relatorio = df[df["id"] == id_relatorio].copy()
            row_relatorio = df_relatorio.iloc[0]

            id_os_relatorio = str(row_relatorio["ID_OS"]).strip()
            veiculo_relatorio = str(row_relatorio["Veiculo"]).strip()

            arquivo = gerar_pdf_em_cache(
                df_relatorio,
                f"Ordem de Serviço: {id_os_relatorio}",
            )

            nome_veiculo = re.sub(r"[^A-Za-z0-9_-]+", "_", veiculo_relatorio).strip("_")
            nome_arquivo = f"Relatorio_{id_os_relatorio}_{nome_veiculo}.pdf"

            st.download_button(
                "Baixar relatório PDF",
                arquivo,
                file_name=nome_arquivo,
                mime="application/pdf",
                use_container_width=True,
                on_click="ignore",
            )

    if pode_gerir_os(nivel_user) and not df_os.empty:
        with st.container(border=True):
            st.subheader("⚙️ Gestão de OS")
            mapa = {f"{r.ID_OS} · {r.Veiculo} · {r.Placa}": r for r in df_os.itertuples()}
            row = mapa[st.selectbox("Selecione a OS", list(mapa.keys()))]
            c1, c2 = st.columns(2)
            with c1:
                label = "Desarquivar" if row.Arquivado == "Sim" else "Arquivar"
                if st.button(label, use_container_width=True):
                    ok, _ = executar(arquivar_chamado, user_data, row.id, row.Arquivado != "Sim", row.Versao)
                    if ok: st.rerun()
            with c2:
                confirma = st.checkbox("Confirmo a remoção desta OS", key=f"del_{row.id}")
                if st.button("🗑️ Remover da operação", disabled=not confirma, use_container_width=True):
                    ok, _ = executar(excluir_chamado, user_data, row.id)
                    if ok: st.rerun()
    st.stop()

# ---------- Triagem ----------
if aba == "Triagem":
    if not pode_triagem(nivel_user):
        st.error("Acesso não autorizado."); st.stop()
    st.header("🎯 Triagem & Prioridades")
    try:
        df_os = carregar_chamados()
    except Exception:
        st.error("Não foi possível carregar os chamados.")
        st.stop()
    pendentes = df_os[(df_os["Aprovado_Coordenador"] == "Não") & (df_os["Arquivado"] != "Sim")]
    if pendentes.empty:
        st.info("Nenhum chamado pendente de aprovação.")
    else:
        for row in pendentes.itertuples():
            with st.expander(f"{row.ID_OS} · {row.Veiculo} ({row.Placa})"):
                st.write(f"**Solicitante:** {row.Motorista} · **Registrado:** {row.Data}")
                st.write(f"**Problema:** {row.Descricao_Problema}")
                prioridade = st.selectbox("Prioridade", PRIORIDADES, key=f"prio_{row.id}")
                if st.button("Aprovar e enviar para oficina", key=f"aprovar_{row.id}", use_container_width=True):
                    ok, _ = executar(aprovar_chamado, user_data, row.id, prioridade, row.Versao)
                    if ok: st.rerun()
    st.stop()

# ---------- Oficina ----------
if aba == "Oficina":
    if not pode_ver_oficina(nivel_user):
        st.error("Acesso não autorizado."); st.stop()
    st.header("🛠️ Painel da Oficina")
    try:
        df_os = carregar_chamados()
    except Exception:
        st.error("Não foi possível carregar os chamados.")
        st.stop()
    aprovados = df_os[(df_os["Aprovado_Coordenador"] == "Sim") & (df_os["Arquivado"] != "Sim")]
    t1, t2, t3, t4 = st.tabs(["⏳ Em Aberto", "🔄 Em Andamento", "✅ Concluídos Recentes", "🔍 Histórico"])

    def renderizar(df_sub):
        if df_sub.empty:
            st.info("Nenhum chamado nesta categoria."); return
        for row in df_sub.itertuples():
            with st.expander(f"[{row.Prioridade}] {row.ID_OS} · {row.Veiculo} ({row.Placa})"):
                st.write(f"**Solicitante:** {row.Motorista} · **Registro:** {row.Data}")
                st.write(f"**Problema:** {row.Descricao_Problema}")

                # OS concluída é somente consulta para usuários comuns.
                # O Administrador Global recebe uma ação excepcional e explícita de reabertura.
                if row.Status == "Concluído":
                    st.write("**Status:** Concluído")
                    mecanico_atual = str(row.Mecanico_Responsavel or "").strip()
                    st.write(f"**Mecânico responsável:** {mecanico_atual if mecanico_atual not in {'', 'nan', 'None'} else 'Não informado'}")

                    data_conclusao = row.Data_Liberacao_dt
                    try:
                        data_conclusao = pd.to_datetime(data_conclusao, utc=True, errors="coerce")
                        if pd.notna(data_conclusao):
                            data_conclusao = data_conclusao.tz_convert("America/Bahia").strftime("%d/%m/%Y %H:%M")
                        else:
                            data_conclusao = "Não informada"
                    except Exception:
                        data_conclusao = "Não informada"
                    st.write(f"**Data de conclusão:** {data_conclusao}")

                    if pode_gerir_os(nivel_user):
                        st.divider()
                        st.caption("🔓 Administrador Global: use esta ação somente para corrigir uma conclusão indevida. A reabertura será registrada na Auditoria.")
                        confirmar_reabertura = st.checkbox(
                            "Confirmo a reabertura desta OS",
                            key=f"conf_reabrir_{row.id}",
                        )
                        if st.button(
                            "Reabrir OS",
                            key=f"reabrir_{row.id}",
                            disabled=not confirmar_reabertura,
                            use_container_width=True,
                        ):
                            ok, _ = executar(
                                atualizar_oficina,
                                user_data,
                                row.id,
                                "Em Andamento",
                                mecanico_atual,
                                row.Versao,
                            )
                            if ok: st.rerun()
                    continue

                fluxo_status = ["Aguardando Manutenção", "Em Andamento", "Concluído"]
                if row.Status in fluxo_status:
                    indice_atual = fluxo_status.index(row.Status)
                    op = fluxo_status if pode_gerir_os(nivel_user) else fluxo_status[indice_atual:]
                else:
                    op = fluxo_status

                novo_status = st.selectbox(
                    "Status",
                    op,
                    index=op.index(row.Status) if row.Status in op else 0,
                    key=f"status_{row.id}",
                )
                bloqueado = str(row.Mecanico_Responsavel or "").strip() not in {"", "Não Atribuído", "nan", "None"}
                mecanico = st.text_input("Mecânico responsável", value=row.Mecanico_Responsavel if bloqueado else "", disabled=bloqueado, key=f"mec_{row.id}")
                if bloqueado: st.caption("🔒 O responsável fica fixo após a primeira atribuição.")
                confirmar = st.checkbox("Confirmo esta atualização", key=f"conf_of_{row.id}")
                if st.button("Salvar alterações", key=f"save_{row.id}", disabled=not confirmar, use_container_width=True):
                    ok, _ = executar(atualizar_oficina, user_data, row.id, novo_status, mecanico, row.Versao)
                    if ok: st.rerun()

    with t1: renderizar(aprovados[aprovados["Status"] == "Aguardando Manutenção"])
    with t2: renderizar(aprovados[aprovados["Status"] == "Em Andamento"])
    with t3:
        lim = datetime.now(timezone.utc) - timedelta(days=2)
        recentes = aprovados[(aprovados["Status"] == "Concluído") & (pd.to_datetime(aprovados["Data_Liberacao_dt"], utc=True, errors="coerce") >= lim)]
        renderizar(recentes)
    with t4:
        f1, f2, f3 = st.columns(3)
        with f1: fs = st.selectbox("Status", ["Todos", "Aguardando Aprovação", "Aguardando Manutenção", "Em Andamento", "Concluído"], key="hist_s")
        with f2: fm = st.text_input("Mecânico", key="hist_m")
        with f3: fp = st.text_input("Placa / ID", key="hist_p")
        hist = df_os.copy()
        if fs != "Todos": hist = hist[hist["Status"] == fs]
        if fm.strip(): hist = hist[hist["Mecanico_Responsavel"].astype(str).str.contains(fm, case=False, na=False)]
        if fp.strip(): hist = hist[hist["Placa"].astype(str).str.contains(fp, case=False, na=False) | hist["ID_OS"].astype(str).str.contains(fp, case=False, na=False)]
        st.dataframe(hist[["ID_OS", "Data", "Veiculo", "Placa", "Status", "Prioridade", "Mecanico_Responsavel", "Data_Liberacao"]], use_container_width=True, hide_index=True)
    st.stop()


# ---------- Minha senha ----------
if aba == "Minha Senha":
    # Usuários que já possuem Gestão de Usuários usam a área administrativa.
    if pode_gerir_usuarios(nivel_user):
        st.error("Acesso não autorizado."); st.stop()

    st.header("🔑 Alterar minha senha")
    st.caption("Para sua segurança, informe a senha atual antes de definir uma nova.")

    with st.form("alterar_minha_senha", clear_on_submit=True):
        senha_atual = st.text_input("Senha atual", type="password")
        nova_senha = st.text_input(
            "Nova senha",
            type="password",
            help="Mínimo de 8 caracteres, com maiúscula, minúscula e número.",
        )
        confirmar_nova = st.text_input("Confirmar nova senha", type="password")
        alterar = st.form_submit_button("Alterar senha", use_container_width=True)

    if alterar:
        if nova_senha != confirmar_nova:
            st.error("A confirmação da nova senha não confere.")
        else:
            ok, _ = executar(
                alterar_propria_senha,
                user_data,
                senha_atual,
                nova_senha,
            )
            if ok:
                sair("Senha alterada com sucesso. Entre novamente com a nova senha.")
    st.stop()


# ---------- Usuários ----------
if aba == "Usuarios":
    if not pode_gerir_usuarios(nivel_user):
        st.error("Acesso não autorizado."); st.stop()
    st.header("👤 Gestão de Usuários")
    opcoes_nivel = {"1 - Motorista": 1.0, "2 - Operacional": 2.0, "3 - Coordenador": 3.0}
    if nivel_user >= 4.0: opcoes_nivel["3.5 - Coordenador Plus"] = 3.5
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ Novo Usuário")
        with st.form("novo_usuario", clear_on_submit=True):
            nome = st.text_input("Nome completo")
            username = normalizar_usuario(st.text_input("Usuário (login)"))
            senha = st.text_input("Senha", type="password", help="Mínimo de 8 caracteres, com maiúscula, minúscula e número.")
            nivel_label = st.selectbox("Nível de acesso", list(opcoes_nivel.keys()))
            cadastrar = st.form_submit_button("Cadastrar", use_container_width=True)
        if cadastrar:
            ok, _ = executar(criar_usuario, user_data, username, senha, nome, opcoes_nivel[nivel_label])
            if ok: st.rerun()
    with c2:
        st.subheader("⚙️ Gerenciar Usuário")
        usuarios = carregar_usuarios()
        if usuarios.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            ativos = usuarios[usuarios["ativo"] == True]
            if ativos.empty:
                st.info("Nenhum usuário ativo disponível para gerenciamento.")
            else:
                mapa = {f"{r.nome} ({r.usuario})": r for r in ativos.itertuples()}
                escolha = st.selectbox("Selecione o usuário", list(mapa.keys()))
                alvo = mapa[escolha]
                st.write(f"**Nome:** {alvo.nome} · **Login:** `{alvo.usuario}` · **Nível:** {alvo.nivel:g}")
                with st.expander("Alterar nome"):
                    novo_nome = st.text_input("Novo nome completo", value=alvo.nome, key=f"nome_{alvo.usuario}")
                    if st.button("Salvar nome", key=f"sn_{alvo.usuario}", use_container_width=True):
                        ok, _ = executar(alterar_nome, user_data, alvo.usuario, novo_nome)
                        if ok: recarregar_usuario_logado(forcar=True); st.rerun()
                with st.expander("Alterar nível"):
                    novo_label = st.selectbox("Novo nível", list(opcoes_nivel.keys()), key=f"nivel_{alvo.usuario}")
                    permitido = alvo.usuario != usuario_atual and pode_editar_usuario(nivel_user, float(alvo.nivel))
                    if st.button("Salvar nível", key=f"sl_{alvo.usuario}", disabled=not permitido, use_container_width=True):
                        ok, _ = executar(alterar_nivel, user_data, alvo.usuario, opcoes_nivel[novo_label])
                        if ok: st.rerun()
                with st.expander("Redefinir senha"):
                    nova = st.text_input("Nova senha", type="password", key=f"pwd_{alvo.usuario}", help="Mínimo de 8 caracteres, com maiúscula, minúscula e número.")
                    pode_resetar = alvo.usuario == usuario_atual or pode_editar_usuario(nivel_user, float(alvo.nivel))
                    if st.button("Atualizar senha", key=f"sp_{alvo.usuario}", disabled=not pode_resetar, use_container_width=True):
                        executar(redefinir_senha, user_data, alvo.usuario, nova, sucesso="Senha atualizada.")
                with st.expander("Desativar conta"):
                    permitido = alvo.usuario != usuario_atual and pode_editar_usuario(nivel_user, float(alvo.nivel))
                    confirma = st.checkbox("Confirmo a desativação", key=f"conf_u_{alvo.usuario}")
                    if st.button("Desativar conta", key=f"du_{alvo.usuario}", disabled=not (permitido and confirma), use_container_width=True):
                        ok, _ = executar(excluir_usuario, user_data, alvo.usuario)
                        if ok: st.rerun()

    st.divider()
    if "usuarios" not in locals():
        usuarios = carregar_usuarios()

    def formatar_data_usuario(serie):
        return (
            pd.to_datetime(serie, utc=True, errors="coerce")
            .dt.tz_convert("America/Bahia")
            .dt.strftime("%d/%m/%Y %H:%M")
            .fillna("")
        )

    ativos = usuarios[usuarios["ativo"] == True] if not usuarios.empty else usuarios
    st.subheader("✅ Usuários ativos")
    if ativos.empty:
        st.info("Nenhum usuário ativo.")
    else:
        tabela_ativos = ativos[["usuario", "nome", "nivel", "criado_em", "atualizado_em"]].copy()
        tabela_ativos["criado_em"] = formatar_data_usuario(tabela_ativos["criado_em"])
        tabela_ativos["atualizado_em"] = formatar_data_usuario(tabela_ativos["atualizado_em"])
        tabela_ativos = tabela_ativos.rename(columns={
            "usuario": "Usuário", "nome": "Nome", "nivel": "Nível",
            "criado_em": "Criado em", "atualizado_em": "Atualizado em"
        })
        st.dataframe(tabela_ativos, use_container_width=True, hide_index=True)

    inativos = usuarios[usuarios["ativo"] == False] if not usuarios.empty else usuarios
    with st.expander(f"⛔ Usuários desativados ({len(inativos)})", expanded=False):
        if inativos.empty:
            st.info("Nenhum usuário desativado.")
        else:
            tabela_inativos = inativos[["usuario", "nome", "nivel", "atualizado_em"]].copy()
            tabela_inativos["atualizado_em"] = formatar_data_usuario(tabela_inativos["atualizado_em"])
            tabela_inativos = tabela_inativos.rename(columns={
                "usuario": "Usuário", "nome": "Nome", "nivel": "Nível",
                "atualizado_em": "Desativado / atualizado em"
            })
            st.dataframe(tabela_inativos, use_container_width=True, hide_index=True)
            mapa_inativos = {f"{r.nome} ({r.usuario})": r for r in inativos.itertuples()}
            escolha_inativo = st.selectbox("Selecione uma conta para reativar", list(mapa_inativos.keys()), key="reativar_usuario_sel")
            alvo_inativo = mapa_inativos[escolha_inativo]
            pode_reativar = pode_editar_usuario(nivel_user, float(alvo_inativo.nivel))
            confirma_reativacao = st.checkbox("Confirmo a reativação", key=f"conf_reativar_{alvo_inativo.usuario}")
            if st.button("♻️ Reativar conta", key=f"reativar_{alvo_inativo.usuario}", disabled=not (pode_reativar and confirma_reativacao), use_container_width=True):
                ok, _ = executar(reativar_usuario, user_data, alvo_inativo.usuario, sucesso="Conta reativada com sucesso.")
                if ok: st.rerun()
    st.stop()

# ---------- Auditoria ----------
if aba == "Auditoria":
    if not pode_gerir_os(nivel_user):
        st.error("Acesso não autorizado."); st.stop()
    st.header("🧾 Auditoria do Sistema")
    st.caption("Registro das ações administrativas e operacionais mais importantes.")
    aud = carregar_auditoria(500)
    if aud.empty:
        st.info("Ainda não há eventos de auditoria.")
    else:
        aud["criado_em"] = pd.to_datetime(aud["criado_em"], utc=True).dt.tz_convert("America/Bahia").dt.strftime("%d/%m/%Y %H:%M:%S")
        st.dataframe(aud[["criado_em", "ator", "acao", "entidade", "entidade_id", "detalhes"]], use_container_width=True, hide_index=True)
    st.stop()

st.error("Página inválida.")
