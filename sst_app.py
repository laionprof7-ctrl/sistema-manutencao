from __future__ import annotations

import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from sst_database import inicializar_banco_sst
from sst_reports import gerar_pdf_documento
from sst_ui import aplicar_estilo_sst, mostrar_notificacao, renderizar_cabecalho_modulo, renderizar_card_texto
from sst_services import (
    MOTIVOS_ENTREGA,
    MOTIVOS_OS,
    adicionar_vinculo_ghe,
    atualizar_conteudo_ghe,
    atualizar_validade_epi,
    cadastrar_colaborador,
    cadastrar_epi,
    cadastrar_ghe,
    criar_ordem_servico_sst,
    definir_status_colaborador,
    definir_status_epi,
    definir_status_ghe,
    fechar_documento_para_assinatura,
    listar_colaboradores,
    listar_documentos,
    listar_entregas,
    listar_epis,
    listar_ghes,
    listar_pendentes_assinatura,
    listar_vinculos_ghe,
    obter_documento,
    obter_pdf_documento,
    obter_resumo_dashboard_sst,
    registrar_entrega_epi,
    vincular_colaborador_ghe,
)

TZ_BAHIA = ZoneInfo("America/Bahia")
UNIDADES_EPI = ["unidade", "par", "caixa", "pacote", "kit", "rolo", "frasco", "litro", "metro"]


@st.cache_resource(show_spinner=False)
def _inicializar_sst_uma_vez() -> bool:
    inicializar_banco_sst()
    return True


@st.cache_data(ttl=30, show_spinner=False)
def _resumo_dashboard_cache() -> dict:
    return obter_resumo_dashboard_sst()


@st.cache_data(ttl=30, show_spinner=False)
def _colaboradores_cache(apenas_ativos: bool) -> list[dict]:
    return listar_colaboradores(apenas_ativos=apenas_ativos)


@st.cache_data(ttl=30, show_spinner=False)
def _epis_cache(apenas_ativos: bool) -> list[dict]:
    return listar_epis(apenas_ativos=apenas_ativos)


@st.cache_data(ttl=20, show_spinner=False)
def _ghes_cache(apenas_ativos: bool) -> list[dict]:
    return listar_ghes(apenas_ativos=apenas_ativos)


@st.cache_data(ttl=20, show_spinner=False)
def _vinculos_ghe_cache(apenas_ativos: bool) -> list[dict]:
    return listar_vinculos_ghe(apenas_ativos=apenas_ativos)


@st.cache_data(ttl=20, show_spinner=False)
def _entregas_cache(limite: int) -> list[dict]:
    return listar_entregas(limite=limite)


@st.cache_data(ttl=20, show_spinner=False)
def _documentos_cache(limite: int, colaborador_id, tipo, status, data_inicio, data_fim, busca) -> list[dict]:
    return listar_documentos(
        limite=limite,
        colaborador_id=colaborador_id,
        tipo=tipo,
        status=status,
        data_inicio=data_inicio,
        data_fim=data_fim,
        busca=busca,
    )


@st.cache_data(ttl=20, show_spinner=False)
def _pendentes_cache(limite: int = 100) -> list[dict]:
    return listar_pendentes_assinatura(limite=limite)


def _limpar_caches_sst() -> None:
    for fn in (
        _resumo_dashboard_cache,
        _colaboradores_cache,
        _epis_cache,
        _ghes_cache,
        _vinculos_ghe_cache,
        _entregas_cache,
        _documentos_cache,
        _pendentes_cache,
    ):
        fn.clear()


def _executar(operacao, *args, **kwargs):
    try:
        return True, operacao(*args, **kwargs)
    except Exception as exc:
        st.error(str(exc))
        return False, None


def _data_hora(valor) -> str:
    if not valor:
        return "—"
    try:
        return valor.astimezone(TZ_BAHIA).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _data(valor) -> str:
    if not valor:
        return "—"
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _mascarar_cpf(cpf: str | None) -> str:
    if not cpf:
        return "—"
    dig = "".join(c for c in cpf if c.isdigit())
    if len(dig) != 11:
        return "—"
    return f"***.{dig[3:6]}.{dig[6:9]}-**"


def _tabela_historico_entregas(entregas: list[dict]) -> None:
    if not entregas:
        st.info("Nenhuma entrega registrada.")
        return
    linhas = []
    for r in entregas:
        epi_ca = html.escape(str(r["epi"]))
        if r.get("ca"):
            epi_ca += f" · CA {html.escape(str(r['ca']))}"
        linhas.append(
            "<tr>"
            f"<td>{html.escape(_data_hora(r['entregue_em']))}</td>"
            f"<td>{html.escape(str(r['colaborador']))}</td>"
            f"<td>{html.escape(str(r.get('matricula') or '—'))}</td>"
            f"<td>{epi_ca}</td>"
            f"<td>{html.escape(str(r.get('motivo_entrega') or '—'))}</td>"
            f"<td class='qtd'>{int(r['quantidade'])}</td>"
            "</tr>"
        )
    st.markdown(
        """
        <style>
        .sst-table-wrap {overflow-x:auto; border:1px solid rgba(128,128,128,.22); border-radius:8px;}
        table.sst-table {width:100%; border-collapse:collapse; font-size:0.92rem;}
        .sst-table th,.sst-table td {padding:10px 12px; border-bottom:1px solid rgba(128,128,128,.18); text-align:left;}
        .sst-table th {font-weight:600; background:rgba(128,128,128,.06);}
        .sst-table td.qtd,.sst-table th.qtd {text-align:center !important; width:90px;}
        .sst-table tr:last-child td {border-bottom:0;}
        </style>
        <div class="sst-table-wrap"><table class="sst-table">
        <thead><tr><th>Data</th><th>Colaborador</th><th>Matrícula</th><th>EPI / CA</th><th>Motivo</th><th class="qtd">Quantidade</th></tr></thead>
        <tbody>""" + "".join(linhas) + """</tbody></table></div>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("Confirmar ação")
def _confirmar_acao(titulo: str, resumo: list[tuple[str, str]], acao, mensagem: str):
    st.warning("Tem certeza que deseja realizar esta ação? Ela será registrada no histórico.")
    st.markdown(f"**{titulo}**")
    for rotulo, valor in resumo:
        st.write(f"**{rotulo}:** {valor}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Confirmar", type="primary", use_container_width=True):
        ok, resultado = _executar(acao)
        if ok:
            _limpar_caches_sst()
            st.session_state["sst_mensagem"] = mensagem.format(resultado=resultado)
            st.rerun()


# --------------------------- GHE ---------------------------

def _render_ghes(actor: dict) -> None:
    st.subheader("GHE / Funções e Setores")
    st.caption("O GHE centraliza o conteúdo técnico da Ordem de Serviço e pode atender mais de uma função/setor.")

    with st.expander("➕ Cadastrar GHE"):
        with st.form("sst_form_ghe"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código do GHE", max_chars=40)
            nome = c2.text_input("Nome / identificação do GHE", max_chars=160)
            setor = c1.text_input("Setor inicial", max_chars=160)
            funcao = c2.text_input("Função inicial", max_chars=160)
            riscos = st.text_area("Riscos ocupacionais", height=110, max_chars=50000)
            medidas = st.text_area("Medidas preventivas", height=110, max_chars=50000)
            epis = st.text_area("EPIs recomendados", height=100, max_chars=50000)
            orientacoes = st.text_area("Orientações / procedimentos de segurança", height=140, max_chars=50000)
            enviado = st.form_submit_button("Cadastrar GHE", use_container_width=True)
        if enviado:
            _confirmar_acao(
                "Cadastro de GHE",
                [("GHE", codigo), ("Nome", nome), ("Setor", setor), ("Função", funcao)],
                lambda: cadastrar_ghe(actor, codigo, nome, setor, funcao, riscos, medidas, epis, orientacoes),
                "GHE cadastrado com sucesso.",
            )

    ok_g, ghes = _executar(_ghes_cache, False)
    ok_v, vinculos = _executar(_vinculos_ghe_cache, False)
    if not (ok_g and ok_v):
        return
    if not ghes:
        st.info("Nenhum GHE cadastrado.")
        return

    qtd_vinculos = {}
    for v in vinculos:
        qtd_vinculos[int(v["ghe_id"])] = qtd_vinculos.get(int(v["ghe_id"]), 0) + 1
    st.dataframe([
        {
            "Código": g["codigo"], "GHE": g["nome"], "Vínculos setor/função": qtd_vinculos.get(int(g["id"]), 0),
            "Status": "Ativo" if g["ativo"] else "Inativo",
        } for g in ghes
    ], use_container_width=True, hide_index=True)

    ativos = [g for g in ghes if g["ativo"]]
    if ativos:
        with st.expander("➕ Adicionar função/setor a um GHE"):
            mapa = {f"{g['codigo']} · {g['nome']}": g for g in ativos}
            escolha = st.selectbox("GHE", list(mapa), key="sst_ghe_add_vinculo")
            c1, c2 = st.columns(2)
            setor_novo = c1.text_input("Setor", key="sst_ghe_vinc_setor")
            funcao_nova = c2.text_input("Função", key="sst_ghe_vinc_funcao")
            if st.button("Adicionar vínculo", use_container_width=True):
                alvo = mapa[escolha]
                _confirmar_acao(
                    "Adicionar função/setor ao GHE",
                    [("GHE", alvo["codigo"]), ("Setor", setor_novo), ("Função", funcao_nova)],
                    lambda: adicionar_vinculo_ghe(actor, int(alvo["id"]), setor_novo, funcao_nova),
                    "Vínculo adicionado ao GHE.",
                )

        with st.expander("📝 Atualizar conteúdo técnico do GHE"):
            mapa = {f"{g['codigo']} · {g['nome']}": g for g in ativos}
            escolha = st.selectbox("GHE", list(mapa), key="sst_ghe_editar")
            alvo = mapa[escolha]
            riscos = st.text_area("Riscos ocupacionais", value=alvo.get("riscos") or "", height=100, key=f"sst_ghe_riscos_{alvo['id']}")
            medidas = st.text_area("Medidas preventivas", value=alvo.get("medidas_preventivas") or "", height=100, key=f"sst_ghe_medidas_{alvo['id']}")
            epis = st.text_area("EPIs recomendados", value=alvo.get("epis_recomendados") or "", height=90, key=f"sst_ghe_epis_{alvo['id']}")
            orientacoes = st.text_area("Orientações / procedimentos de segurança", value=alvo.get("orientacoes") or "", height=130, key=f"sst_ghe_orient_{alvo['id']}")
            if st.button("Salvar conteúdo técnico", use_container_width=True):
                _confirmar_acao(
                    "Atualização do conteúdo técnico",
                    [("GHE", alvo["codigo"]), ("Nome", alvo["nome"])],
                    lambda: atualizar_conteudo_ghe(actor, int(alvo["id"]), riscos, medidas, epis, orientacoes),
                    "Conteúdo técnico do GHE atualizado.",
                )

    with st.expander("🔄 Ativar / desativar GHE"):
        mapa = {f"{g['codigo']} · {g['nome']} · {'Ativo' if g['ativo'] else 'Inativo'}": g for g in ghes}
        escolha = st.selectbox("GHE", list(mapa), key="sst_ghe_status")
        alvo = mapa[escolha]
        novo = not bool(alvo["ativo"])
        if st.button("Reativar GHE" if novo else "Desativar GHE", use_container_width=True):
            _confirmar_acao(
                "Alteração de status do GHE",
                [("GHE", alvo["codigo"]), ("Novo status", "Ativo" if novo else "Inativo")],
                lambda: definir_status_ghe(actor, int(alvo["id"]), novo),
                "Status do GHE atualizado.",
            )


# ---------------------- COLABORADORES ----------------------

def _render_colaboradores(actor: dict) -> None:
    st.subheader("Colaboradores")
    ok_v, vinculos = _executar(_vinculos_ghe_cache, True)
    if not ok_v:
        return

    with st.expander("➕ Cadastrar colaborador"):
        @st.fragment
        def _cadastro_colaborador_fragmento():
            f1, f2 = st.columns(2)
            nome = f1.text_input("Nome completo", key="sst_cad_nome")
            matricula = f2.text_input("Matrícula", key="sst_cad_matricula")
            cpf = f1.text_input("CPF", key="sst_cad_cpf")

            mapa_v = {
                f"{v['ghe_codigo']} · {v['setor']} · {v['funcao']}": v for v in vinculos
            }
            if mapa_v:
                vinculo_label = f2.selectbox("GHE / Setor / Função", list(mapa_v), key="sst_cad_vinculo_ghe")
                vinculo = mapa_v[vinculo_label]
                f1.text_input("Setor", value=vinculo["setor"], disabled=True, key=f"sst_cad_setor_visual_{vinculo['vinculo_id']}")
                f2.text_input("Função", value=vinculo["funcao"], disabled=True, key=f"sst_cad_funcao_visual_{vinculo['vinculo_id']}")
            else:
                vinculo = None
                st.info("Cadastre um GHE com setor/função antes de cadastrar novos colaboradores.")

            def _resetar_data_admissao():
                if not st.session_state.get("sst_informar_data_admissao", False):
                    st.session_state["sst_cad_data_admissao"] = datetime.now(TZ_BAHIA).date()

            informar = f1.checkbox("Informar data de admissão", key="sst_informar_data_admissao", on_change=_resetar_data_admissao)
            data_admissao = f2.date_input("Data de admissão", value=datetime.now(TZ_BAHIA).date(), format="DD/MM/YYYY", disabled=not informar, key="sst_cad_data_admissao")

            enviado = st.button("Cadastrar colaborador", key="sst_btn_cadastrar_colaborador", type="primary", use_container_width=True, disabled=vinculo is None)
            if enviado and vinculo:
                dados = {
                    "nome": nome, "cpf": cpf, "matricula": matricula,
                    "funcao": vinculo["funcao"], "setor": vinculo["setor"], "ghe_id": int(vinculo["ghe_id"]),
                    "data_admissao": data_admissao,
                }
                _confirmar_acao(
                    "Cadastro de colaborador",
                    [("Nome", nome), ("Matrícula", matricula or "—"), ("GHE", vinculo["ghe_codigo"]), ("Função", vinculo["funcao"]), ("Setor", vinculo["setor"]), ("Admissão", _data(data_admissao))],
                    lambda: cadastrar_colaborador(actor, **dados),
                    "Colaborador cadastrado com sucesso.",
                )
        _cadastro_colaborador_fragmento()

    ok, colaboradores = _executar(_colaboradores_cache, False)
    if not ok:
        return
    if not colaboradores:
        st.info("Nenhum colaborador cadastrado.")
        return
    colaboradores = sorted(colaboradores, key=lambda r: str(r.get("nome") or "").casefold())
    filtro = st.segmented_control("Filtrar colaboradores", options=["Todos", "Ativos", "Inativos"], default="Todos", key="sst_filtro_status_colaboradores")
    if filtro == "Ativos": filtrados = [r for r in colaboradores if bool(r["ativo"])]
    elif filtro == "Inativos": filtrados = [r for r in colaboradores if not bool(r["ativo"])]
    else: filtrados = colaboradores
    if filtrados:
        st.dataframe([
            {
                "Nome": r["nome"], "Matrícula": r.get("matricula") or "—", "CPF": _mascarar_cpf(r.get("cpf")),
                "Função": r.get("funcao") or "—", "Setor": r.get("setor") or "—",
                "GHE": r.get("ghe_codigo") or "Não vinculado", "Admissão": _data(r.get("data_admissao")),
                "Status": "Ativo" if r["ativo"] else "Inativo",
            } for r in filtrados
        ], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum colaborador encontrado neste filtro.")

    if vinculos:
        with st.expander("🔗 Vincular / alterar GHE do colaborador"):
            mapa_c = {f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r for r in colaboradores}
            mapa_v = {f"{v['ghe_codigo']} · {v['setor']} · {v['funcao']}": v for v in vinculos}
            ec = st.selectbox("Colaborador", list(mapa_c), key="sst_vinc_colab")
            ev = st.selectbox("GHE / Setor / Função", list(mapa_v), key="sst_vinc_ghe")
            if st.button("Salvar vínculo", use_container_width=True):
                col = mapa_c[ec]; vin = mapa_v[ev]
                _confirmar_acao(
                    "Vincular colaborador ao GHE",
                    [("Colaborador", col["nome"]), ("GHE", vin["ghe_codigo"]), ("Setor", vin["setor"]), ("Função", vin["funcao"])],
                    lambda: vincular_colaborador_ghe(actor, int(col["id"]), int(vin["ghe_id"]), vin["setor"], vin["funcao"]),
                    "GHE do colaborador atualizado.",
                )

    with st.expander("🔄 Ativar / desativar colaborador"):
        mapa = {f"{r['nome']} · {'Ativo' if r['ativo'] else 'Inativo'}": r for r in colaboradores}
        escolha = st.selectbox("Colaborador", list(mapa), key="sst_gerir_colaborador")
        alvo = mapa[escolha]; novo = not bool(alvo["ativo"])
        if st.button("Reativar" if novo else "Desativar", use_container_width=True):
            _confirmar_acao("Alteração de status", [("Colaborador", alvo["nome"]), ("Novo status", "Ativo" if novo else "Inativo")], lambda: definir_status_colaborador(actor, int(alvo["id"]), novo), "Status do colaborador atualizado.")


# --------------------------- EPIs --------------------------

def _cadastrar_epi_e_limpar(actor: dict, dados: dict):
    resultado = cadastrar_epi(actor, **dados)
    st.session_state["sst_epi_nome"] = ""
    st.session_state["sst_epi_ca"] = ""
    st.session_state["sst_epi_fabricante"] = ""
    st.session_state["sst_epi_validade"] = datetime.now(TZ_BAHIA).date()
    st.session_state["sst_epi_unidade"] = UNIDADES_EPI[0]
    return resultado


def _render_epis(actor: dict) -> None:
    st.subheader("EPIs")
    with st.expander("➕ Cadastrar EPI"):
        @st.fragment
        def _cadastro_epi_fragmento():
            c1, c2 = st.columns(2)
            nome = c1.text_input("EPI", key="sst_epi_nome")
            ca = c2.text_input("CA", key="sst_epi_ca")
            fabricante = c1.text_input("Fabricante", key="sst_epi_fabricante")
            validade = c2.date_input("Validade do CA", value=datetime.now(TZ_BAHIA).date(), format="DD/MM/YYYY", key="sst_epi_validade")
            unidade = c1.selectbox("Unidade", UNIDADES_EPI, key="sst_epi_unidade")
            enviado = st.button("Cadastrar EPI", key="sst_btn_cadastrar_epi", type="primary", use_container_width=True)
            if enviado:
                dados = {"nome": nome, "ca": ca, "fabricante": fabricante, "unidade": unidade, "validade_ca": validade}
                _confirmar_acao(
                    "Cadastro de EPI",
                    [("EPI", nome), ("CA", ca), ("Fabricante", fabricante.strip() if fabricante and fabricante.strip() else "Não informado"), ("Validade do CA", _data(validade)), ("Unidade", unidade)],
                    lambda: _cadastrar_epi_e_limpar(actor, dados), "EPI cadastrado com sucesso.",
                )
        _cadastro_epi_fragmento()

    ok, epis = _executar(_epis_cache, False)
    if not ok: return
    if not epis:
        st.info("Nenhum EPI cadastrado."); return
    hoje = datetime.now(TZ_BAHIA).date()
    proximos = [r for r in epis if r.get("ativo") and r.get("validade_ca") and 0 <= (r["validade_ca"] - hoje).days <= 30]
    if proximos: st.warning(f"{len(proximos)} EPI(s) possui(em) CA com vencimento nos próximos 30 dias.")
    st.dataframe([
        {"EPI": r["nome"], "CA": r.get("ca") or "—", "Validade do CA": _data(r.get("validade_ca")), "Fabricante": r.get("fabricante") or "—", "Unidade": r["unidade"], "Status": "Ativo" if r["ativo"] else "Inativo"}
        for r in epis
    ], use_container_width=True, hide_index=True)
    st.caption("CA vencido desativa o EPI automaticamente para novas entregas, sem apagar o histórico.")
    with st.expander("🔄 Renovar validade / ativar / desativar EPI"):
        mapa = {f"{r['nome']} · CA {r.get('ca') or '—'} · {'Ativo' if r['ativo'] else 'Inativo'}": r for r in epis}
        escolha = st.selectbox("EPI", list(mapa), key="sst_gerir_epi"); alvo = mapa[escolha]
        nova_validade = st.date_input("Nova validade do CA", value=alvo.get("validade_ca") or hoje, format="DD/MM/YYYY", key=f"sst_nova_validade_{alvo['id']}")
        c1, c2 = st.columns(2)
        if c1.button("Salvar validade e reativar", use_container_width=True):
            _confirmar_acao("Renovação do CA", [("EPI", alvo["nome"]), ("CA", alvo.get("ca") or "—"), ("Nova validade", _data(nova_validade))], lambda: atualizar_validade_epi(actor, int(alvo["id"]), nova_validade, True), "Validade do CA atualizada.")
        novo = not bool(alvo["ativo"])
        if c2.button("Reativar" if novo else "Desativar", use_container_width=True):
            _confirmar_acao("Alteração de status do EPI", [("EPI", alvo["nome"]), ("Novo status", "Ativo" if novo else "Inativo")], lambda: definir_status_epi(actor, int(alvo["id"]), novo), "Status do EPI atualizado.")


# ----------------------- ENTREGA EPI -----------------------

def _ids_itens_entrega() -> list[int]:
    if "sst_entrega_item_ids" not in st.session_state:
        st.session_state["sst_entrega_item_ids"] = [1]
        st.session_state["sst_entrega_item_seq"] = 1
    return list(st.session_state["sst_entrega_item_ids"])


def _adicionar_item_entrega() -> None:
    ids = _ids_itens_entrega()
    if len(ids) >= 5: return
    st.session_state["sst_entrega_item_seq"] = int(st.session_state.get("sst_entrega_item_seq", 1)) + 1
    ids.append(st.session_state["sst_entrega_item_seq"])
    st.session_state["sst_entrega_item_ids"] = ids


def _remover_item_entrega(uid: int) -> None:
    ids = _ids_itens_entrega()
    if uid in ids and len(ids) > 1:
        ids.remove(uid)
        st.session_state["sst_entrega_item_ids"] = ids


def _registrar_entrega_e_limpar(actor: dict, colaborador_id: int, itens: list[dict], motivo: str):
    resultado = registrar_entrega_epi(actor, colaborador_id, itens, motivo)
    for uid in _ids_itens_entrega():
        st.session_state.pop(f"sst_entrega_epi_{uid}", None)
        st.session_state.pop(f"sst_entrega_qtd_{uid}", None)
    st.session_state["sst_entrega_item_ids"] = [1]
    st.session_state["sst_entrega_item_seq"] = 1
    st.session_state["sst_entrega_motivo"] = MOTIVOS_ENTREGA[0]
    return resultado


def _render_entregas(actor: dict) -> None:
    st.subheader("Entrega de EPI")
    ok_c, colaboradores = _executar(_colaboradores_cache, True)
    ok_e, epis = _executar(_epis_cache, True)
    if not (ok_c and ok_e): return
    epis = [r for r in epis if r.get("validade_ca") is not None]
    if not colaboradores:
        st.info("Cadastre ou reative um colaborador antes de registrar uma entrega.")
    elif not epis:
        st.info("Cadastre um EPI ativo com CA válido antes de registrar uma entrega.")
    else:
        mapa_c = {f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r for r in colaboradores}
        mapa_e = {f"{r['nome']} · CA {r['ca']} · {r['unidade']}": r for r in epis}

        @st.fragment
        def _entrega_fragmento():
            colab_label = st.selectbox("Colaborador", list(mapa_c), key="sst_entrega_colaborador")
            st.markdown("**Itens da entrega**")
            selecoes = []
            ids = _ids_itens_entrega()
            for pos, uid in enumerate(ids, 1):
                if pos == 1:
                    c_epi, c_qtd = st.columns([4, 1])
                else:
                    c_epi, c_qtd, c_rem = st.columns([4, 1, .65])
                epi_label = c_epi.selectbox(f"EPI {pos}", list(mapa_e), key=f"sst_entrega_epi_{uid}")
                qtd = c_qtd.number_input(f"Qtd. {pos}", 1, 1000, 1, 1, key=f"sst_entrega_qtd_{uid}")
                selecoes.append((epi_label, qtd))
                if pos > 1:
                    c_rem.button("Remover", key=f"sst_entrega_rem_{uid}", on_click=_remover_item_entrega, args=(uid,), use_container_width=True)

            if len(ids) < 5:
                st.button("+ Adicionar mais um item", key="sst_entrega_add", on_click=_adicionar_item_entrega, use_container_width=False)
            else:
                st.caption("Limite de 5 itens por entrega atingido.")

            motivo = st.selectbox("Motivo da entrega", list(MOTIVOS_ENTREGA), key="sst_entrega_motivo")
            if st.button("Registrar entrega", type="primary", use_container_width=True, key="sst_entrega_registrar"):
                colab = mapa_c[colab_label]
                itens = [{"epi_id": int(mapa_e[e]["id"]), "quantidade": int(q)} for e, q in selecoes]
                resumo = [("Colaborador", colab["nome"]), ("Motivo", motivo)]
                for i, (e, q) in enumerate(selecoes, 1): resumo.append((f"EPI {i}", f"{e} · Quantidade {q}"))
                _confirmar_acao(
                    "Entrega de EPI", resumo,
                    lambda: _registrar_entrega_e_limpar(actor, int(colab["id"]), itens, motivo),
                    "Entrega #{resultado} registrada. O PDF foi gerado e enviado automaticamente para Aguardando Assinatura.",
                )
        _entrega_fragmento()

    ok, entregas = _executar(_entregas_cache, 100)
    if ok:
        st.divider(); st.markdown("#### Histórico de entregas"); st.caption("Exibindo até 100 itens mais recentes.")
        _tabela_historico_entregas(entregas)


# ------------------------ DOCUMENTOS -----------------------

def _render_documentos(actor: dict) -> None:
    st.subheader("Documentos / Ordens de Serviço de SST")
    ok_c, colaboradores = _executar(_colaboradores_cache, True)
    if ok_c and colaboradores:
        mapa_c = {f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r for r in colaboradores}
        with st.expander("➕ Emitir Ordem de Serviço de SST"):
            colab_label = st.selectbox("Colaborador", list(mapa_c), key="sst_os_colaborador")
            colab = mapa_c[colab_label]
            c1, c2, c3 = st.columns(3)
            c1.text_input("Função", value=colab.get("funcao") or "—", disabled=True, key=f"sst_os_func_{colab['id']}")
            c2.text_input("Setor", value=colab.get("setor") or "—", disabled=True, key=f"sst_os_setor_{colab['id']}")
            c3.text_input("GHE", value=colab.get("ghe_codigo") or "Não vinculado", disabled=True, key=f"sst_os_ghe_{colab['id']}")
            c4, c5, c6 = st.columns(3)
            c4.text_input("CPF", value=colab.get("cpf") or "—", disabled=True, key=f"sst_os_cpf_{colab['id']}")
            c5.text_input("Matrícula", value=colab.get("matricula") or "—", disabled=True, key=f"sst_os_mat_{colab['id']}")
            c6.text_input("Data de admissão", value=_data(colab.get("data_admissao")), disabled=True, key=f"sst_os_adm_{colab['id']}")
            motivo = st.selectbox("Motivo da emissão", list(MOTIVOS_OS), key="sst_os_motivo")
            if not colab.get("ghe_id"):
                st.warning("Este colaborador ainda não possui GHE vinculado. Faça o vínculo na área Colaboradores antes de emitir a OS.")
            if st.button("Criar Ordem de Serviço", type="primary", use_container_width=True, disabled=not bool(colab.get("ghe_id"))):
                _confirmar_acao(
                    "Emissão de Ordem de Serviço de SST",
                    [("Colaborador", colab["nome"]), ("Função", colab.get("funcao") or "—"), ("Setor", colab.get("setor") or "—"), ("GHE", colab.get("ghe_codigo") or "—"), ("Motivo", motivo)],
                    lambda: criar_ordem_servico_sst(actor, int(colab["id"]), motivo),
                    "Ordem de Serviço criada como rascunho. Confira e feche para assinatura.",
                )

    st.markdown("#### Histórico de documentos")
    f1, f2, f3 = st.columns([1.3, 1, 1])
    mapa_fc = {"Todos": None}
    if ok_c:
        mapa_fc.update({r["nome"]: int(r["id"]) for r in colaboradores})
    colab_f = f1.selectbox("Colaborador", list(mapa_fc), key="sst_doc_filtro_colab")
    tipo_f = f2.selectbox("Tipo", ["Todos", "Ordem de Serviço de SST", "Entrega de EPI"], key="sst_doc_filtro_tipo")
    status_f = f3.selectbox("Status", ["Todos", "Rascunho", "Aguardando Assinatura", "Assinado"], key="sst_doc_filtro_status")
    f4, f5, f6 = st.columns([1, 1, 1.4])
    usar_periodo = f4.checkbox("Filtrar por período", key="sst_doc_usar_periodo")
    hoje = datetime.now(TZ_BAHIA).date()
    inicio = f5.date_input("De", value=hoje - timedelta(days=30), format="DD/MM/YYYY", disabled=not usar_periodo, key="sst_doc_inicio")
    fim = f6.date_input("Até", value=hoje, format="DD/MM/YYYY", disabled=not usar_periodo, key="sst_doc_fim")
    busca = st.text_input(
        "Buscar por número, colaborador, matrícula, título ou motivo",
        key="sst_doc_busca",
        placeholder="Digite para pesquisar...",
    )

    # O usuário não precisa escolher limite técnico. A tela consulta até 100 registros por vez;
    # os demais continuam armazenados e podem ser encontrados pelos filtros e pela busca.
    ok, documentos = _executar(
        _documentos_cache, 100, mapa_fc[colab_f], tipo_f, status_f,
        inicio if usar_periodo else None, fim if usar_periodo else None, busca.strip() or None,
    )
    if not ok: return
    if documentos:
        st.dataframe([
            {"Número": r["numero"], "Data": _data_hora(r["criado_em"]), "Colaborador": r["colaborador"], "Tipo": r["tipo"], "Motivo": r.get("motivo") or "—", "Status": r["status"]}
            for r in documentos
        ], use_container_width=True, hide_index=True)
        st.caption(f"Exibindo {len(documentos)} documento(s) conforme os filtros atuais.")
    else:
        st.info("Nenhum documento encontrado com os filtros atuais.")
        return

    rascunhos = [r for r in documentos if r["status"] == "Rascunho"]
    if rascunhos:
        with st.expander("📄 Gerar PDF e fechar para assinatura"):
            mapa = {f"{r['numero']} · {r['colaborador']} · {r['titulo']}": r for r in rascunhos}
            escolha = st.selectbox("Documento", list(mapa), key="sst_fechar_doc"); alvo = mapa[escolha]
            if st.button("Gerar PDF e fechar", type="primary", use_container_width=True):
                ok_doc, doc = _executar(obter_documento, int(alvo["id"]))
                if ok_doc:
                    pdf = gerar_pdf_documento(doc)
                    tipo_nome = doc["tipo"].replace(" ", "_").replace("/", "-")
                    nome = f"{doc['numero']}_{tipo_nome}.pdf"
                    _confirmar_acao(
                        "Fechar documento para assinatura",
                        [("Documento", doc["numero"]), ("Colaborador", doc["colaborador"]), ("Motivo", doc.get("motivo") or "—")],
                        lambda: fechar_documento_para_assinatura(actor, int(doc["id"]), pdf, nome),
                        "Documento fechado para assinatura. Hash SHA-256 registrado.",
                    )

    fechados = [r for r in documentos if r["status"] in ("Aguardando Assinatura", "Assinado") and r.get("nome_arquivo")]
    if fechados:
        with st.expander("⬇️ Baixar PDF fechado"):
            mapa = {f"{r['numero']} · {r['colaborador']} · {r['status']}": r for r in fechados}
            escolha = st.selectbox("PDF", list(mapa), key="sst_download_doc"); alvo = mapa[escolha]
            ok_pdf, dados = _executar(obter_pdf_documento, int(alvo["id"]))
            if ok_pdf:
                pdf, nome, hash_doc = dados
                st.caption(f"Arquivo selecionado: {nome}")
                st.caption(f"SHA-256: {hash_doc}")
                # A chave depende do documento/hash para impedir que o navegador preserve o botão do PDF anterior.
                st.download_button(
                    "Baixar PDF", data=pdf, file_name=nome, mime="application/pdf", use_container_width=True,
                    on_click="ignore", key=f"sst_download_pdf_{alvo['id']}_{str(hash_doc)[:12]}",
                )


def _render_assinaturas() -> None:
    st.subheader("Assinaturas")
    st.warning("A integração com o leitor biométrico ainda não está habilitada. O sistema preserva o PDF exato e seu hash, mas não simula uma biometria.")
    ok, pendentes = _executar(_pendentes_cache, 100)
    if ok and pendentes:
        st.markdown("#### Aguardando assinatura biométrica")
        st.dataframe([
            {"Número": r["numero"], "Colaborador": r["colaborador"], "Matrícula": r.get("matricula") or "—", "Tipo": r["tipo"], "Título": r["titulo"], "Fechado em": _data_hora(r["fechado_em"])}
            for r in pendentes
        ], use_container_width=True, hide_index=True)
        st.caption("Exibindo até 100 documentos pendentes mais recentes.")
    elif ok:
        st.info("Nenhum documento aguardando assinatura.")


def _render_dashboard(actor: dict) -> None:
    st.markdown("### Visão geral")
    ok, resumo = _executar(_resumo_dashboard_cache)
    if not ok:
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Colaboradores ativos", resumo["colaboradores_ativos"])
    m2.metric("EPIs ativos", resumo["epis_ativos"])
    m3.metric("CA vencendo em 30 dias", resumo["ca_vencendo_30"])
    m4.metric("Aguardando assinatura", resumo["aguardando_assinatura"])


def renderizar_modulo_sst(actor: dict) -> None:
    aplicar_estilo_sst()
    _inicializar_sst_uma_vez()
    # O cron do Supabase é o responsável pela inativação automática diária.
    # As operações de EPI também validam CA no backend, evitando uma chamada extra a cada rerun da interface.
    if mensagem := st.session_state.pop("sst_mensagem", None):
        mostrar_notificacao(mensagem)
    renderizar_cabecalho_modulo()
    opcoes = {
        "📊 Visão geral": _render_dashboard,
        "🧩 GHE / Funções e Setores": _render_ghes,
        "👷 Colaboradores": _render_colaboradores,
        "⛑️ EPIs": _render_epis,
        "📦 Entrega de EPI": _render_entregas,
        "📄 Documentos / OS de SST": _render_documentos,
        "✍️ Assinaturas": lambda _actor: _render_assinaturas(),
    }
    escolha = st.radio("Módulo", list(opcoes), horizontal=True, label_visibility="collapsed", key="sst_aba_ativa")
    opcoes[escolha](actor)
