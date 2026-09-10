from __future__ import annotations

import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from sst_database import inicializar_banco_sst
from sst_reports import gerar_pdf_documento
from sst_ui import aplicar_estilo_sst, mostrar_notificacao, renderizar_cabecalho_modulo, renderizar_card_texto
from sst_services import (
    atualizar_validade_epi,
    cadastrar_colaborador,
    cadastrar_epi,
    criar_documento_sst,
    definir_status_colaborador,
    definir_status_epi,
    fechar_documento_para_assinatura,
    listar_colaboradores,
    listar_documentos,
    listar_entregas,
    listar_epis,
    listar_pendentes_assinatura,
    obter_documento,
    obter_pdf_documento,
    registrar_entrega_epi,
)


TZ_BAHIA = ZoneInfo("America/Bahia")
UNIDADES_EPI = ["unidade", "par", "caixa", "pacote", "kit", "rolo", "frasco", "litro", "metro"]
TIPOS_DOCUMENTO = [
    "Ordem de Serviço de SST",
    "Admissão",
    "Mudança de função",
    "Ciência / Orientação",
    "Treinamento",
    "Entrega de EPI",
    "Outro",
]


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
        .sst-table td.qtd,.sst-table th.qtd {text-align:center !important; width:110px;}
        .sst-table tr:last-child td {border-bottom:0;}
        </style>
        <div class="sst-table-wrap">
        <table class="sst-table">
          <thead><tr>
            <th>Data</th><th>Colaborador</th><th>Matrícula</th><th>EPI / CA</th><th class="qtd">Quantidade</th>
          </tr></thead>
          <tbody>
        """ + "".join(linhas) + """
          </tbody>
        </table>
        </div>
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
            st.session_state["sst_mensagem"] = mensagem.format(resultado=resultado)
            st.rerun()


def _render_colaboradores(actor: dict) -> None:
    st.subheader("Colaboradores")

    with st.expander("➕ Cadastrar colaborador"):

        @st.fragment
        def _cadastro_colaborador_fragmento():
            # Fragmento isolado: qualquer atualização deste cadastro
            # reexecuta apenas esta área, e não a página inteira.
            f1, f2 = st.columns(2)

            nome = f1.text_input("Nome completo", key="sst_cad_nome")
            matricula = f2.text_input("Matrícula", key="sst_cad_matricula")

            cpf = f1.text_input("CPF", key="sst_cad_cpf")
            funcao = f2.text_input("Função", key="sst_cad_funcao")

            setor = f1.text_input("Setor", key="sst_cad_setor")

            def _resetar_data_admissao():
                if not st.session_state.get("sst_informar_data_admissao", False):
                    st.session_state["sst_cad_data_admissao"] = datetime.now(TZ_BAHIA).date()

            informar_admissao = f2.checkbox(
                "Informar data de admissão",
                key="sst_informar_data_admissao",
                on_change=_resetar_data_admissao,
            )

            data_admissao = f2.date_input(
                "Data de admissão",
                value=datetime.now(TZ_BAHIA).date(),
                format="DD/MM/YYYY",
                disabled=not informar_admissao,
                key="sst_cad_data_admissao",
            )

            enviado = st.button(
                "Cadastrar colaborador",
                key="sst_btn_cadastrar_colaborador",
                type="primary",
                use_container_width=True,
            )

            if enviado:
                dados = {
                    "nome": nome,
                    "cpf": cpf,
                    "matricula": matricula,
                    "funcao": funcao,
                    "setor": setor,
                    # A data exibida no campo é sempre a data efetiva da admissão.
                    # O checkbox serve apenas para permitir edição manual.
                    "data_admissao": data_admissao,
                }
                _confirmar_acao(
                    "Cadastro de colaborador",
                    [
                        ("Nome", nome),
                        ("Matrícula", matricula or "—"),
                        ("Função", funcao),
                        ("Setor", setor or "—"),
                        ("Admissão", _data(data_admissao)),
                    ],
                    lambda: cadastrar_colaborador(actor, **dados),
                    "Colaborador cadastrado com sucesso.",
                )

        _cadastro_colaborador_fragmento()

    ok, colaboradores = _executar(listar_colaboradores, apenas_ativos=False)
    if not ok:
        return
    if not colaboradores:
        st.info("Nenhum colaborador cadastrado.")
        return

    # Ordem alfabética padronizada em toda a tela.
    colaboradores = sorted(
        colaboradores,
        key=lambda r: str(r.get("nome") or "").casefold(),
    )

    filtro_status = st.segmented_control(
        "Filtrar colaboradores",
        options=["Todos", "Ativos", "Inativos"],
        default="Todos",
        key="sst_filtro_status_colaboradores",
    )

    if filtro_status == "Ativos":
        colaboradores_filtrados = [r for r in colaboradores if bool(r["ativo"])]
    elif filtro_status == "Inativos":
        colaboradores_filtrados = [r for r in colaboradores if not bool(r["ativo"])]
    else:
        colaboradores_filtrados = colaboradores

    if colaboradores_filtrados:
        tabela = [{
            "Nome": r["nome"],
            "Matrícula": r.get("matricula") or "—",
            "CPF": _mascarar_cpf(r.get("cpf")),
            "Função": r["funcao"],
            "Setor": r.get("setor") or "—",
            "Admissão": _data(r.get("data_admissao")),
            "Status": "Ativo" if r["ativo"] else "Inativo",
        } for r in colaboradores_filtrados]
        st.dataframe(tabela, use_container_width=True, hide_index=True)
    else:
        st.info(f"Nenhum colaborador {filtro_status.lower()} encontrado.")

    with st.expander("⚙️ Ativar / desativar colaborador"):
        mapa = {
            f"{r['nome']} · {r.get('matricula') or 'sem matrícula'} · {'Ativo' if r['ativo'] else 'Inativo'}": r
            for r in colaboradores
        }
        escolha = st.selectbox("Colaborador", list(mapa), key="sst_status_colab")
        alvo = mapa[escolha]
        novo_status = not bool(alvo["ativo"])
        if st.button("Reativar colaborador" if novo_status else "Desativar colaborador", use_container_width=True):
            _confirmar_acao(
                "Alteração de status",
                [("Colaborador", alvo["nome"]), ("Novo status", "Ativo" if novo_status else "Inativo")],
                lambda: definir_status_colaborador(actor, int(alvo["id"]), novo_status),
                "Status do colaborador atualizado.",
            )


def _render_epis(actor: dict) -> None:
    st.subheader("EPIs")

    with st.expander("➕ Cadastrar EPI"):

        @st.fragment
        def _cadastro_epi_fragmento():
            # Fragmento isolado: alterações aqui não rerenderizam a página inteira.
            c1, c2 = st.columns(2)

            nome = c1.text_input("EPI", key="sst_epi_nome")
            ca = c2.text_input("CA", key="sst_epi_ca")

            fabricante = c1.text_input("Fabricante", key="sst_epi_fabricante")
            validade = c2.date_input(
                "Validade do CA",
                value=datetime.now(TZ_BAHIA).date(),
                format="DD/MM/YYYY",
                key="sst_epi_validade",
            )

            unidade = c1.selectbox(
                "Unidade",
                UNIDADES_EPI,
                key="sst_epi_unidade",
            )

            enviado = st.button(
                "Cadastrar EPI",
                key="sst_btn_cadastrar_epi",
                type="primary",
                use_container_width=True,
            )

            if enviado:
                dados = {
                    "nome": nome,
                    "ca": ca,
                    "fabricante": fabricante,
                    "unidade": unidade,
                    "validade_ca": validade,
                }
                _confirmar_acao(
                    "Cadastro de EPI",
                    [
                        ("EPI", nome),
                        ("CA", ca),
                        ("Fabricante", fabricante or "—"),
                        ("Validade", _data(validade)),
                        ("Unidade", unidade),
                    ],
                    lambda: cadastrar_epi(actor, **dados),
                    "EPI cadastrado com sucesso.",
                )

        _cadastro_epi_fragmento()

    ok, epis = _executar(listar_epis, apenas_ativos=False)
    if not ok:
        return
    if not epis:
        st.info("Nenhum EPI cadastrado.")
        return

    hoje = datetime.now(TZ_BAHIA).date()
    proximos = [r for r in epis if r.get("ativo") and r.get("validade_ca") and 0 <= (r["validade_ca"] - hoje).days <= 30]
    if proximos:
        st.warning(f"{len(proximos)} EPI(s) possui(em) CA com vencimento nos próximos 30 dias.")

    tabela = [{
        "EPI": r["nome"],
        "CA": r.get("ca") or "—",
        "Validade do CA": _data(r.get("validade_ca")),
        "Fabricante": r.get("fabricante") or "—",
        "Unidade": r["unidade"],
        "Status": "Ativo" if r["ativo"] else "Inativo",
    } for r in epis]
    st.dataframe(tabela, use_container_width=True, hide_index=True)
    st.caption("CA vencido desativa o EPI automaticamente para novas entregas, sem apagar o histórico.")

    with st.expander("🔄 Renovar validade / ativar / desativar EPI"):
        mapa = {f"{r['nome']} · CA {r.get('ca') or '—'} · {'Ativo' if r['ativo'] else 'Inativo'}": r for r in epis}
        escolha = st.selectbox("EPI", list(mapa), key="sst_gerir_epi")
        alvo = mapa[escolha]
        nova_validade = st.date_input(
            "Nova validade do CA",
            value=alvo.get("validade_ca") or hoje,
            format="DD/MM/YYYY",
            key=f"sst_nova_validade_{alvo['id']}",
        )
        c1, c2 = st.columns(2)
        if c1.button("Salvar validade e reativar", use_container_width=True):
            _confirmar_acao(
                "Renovação do CA",
                [("EPI", alvo["nome"]), ("CA", alvo.get("ca") or "—"), ("Nova validade", _data(nova_validade))],
                lambda: atualizar_validade_epi(actor, int(alvo["id"]), nova_validade, True),
                "Validade do CA atualizada.",
            )
        novo_status = not bool(alvo["ativo"])
        if c2.button("Reativar" if novo_status else "Desativar", use_container_width=True):
            _confirmar_acao(
                "Alteração de status do EPI",
                [("EPI", alvo["nome"]), ("Novo status", "Ativo" if novo_status else "Inativo")],
                lambda: definir_status_epi(actor, int(alvo["id"]), novo_status),
                "Status do EPI atualizado.",
            )


def _render_entregas(actor: dict) -> None:
    st.subheader("Entrega de EPI")
    ok_c, colaboradores = _executar(listar_colaboradores, apenas_ativos=True)
    ok_e, epis = _executar(listar_epis, apenas_ativos=True)
    if not (ok_c and ok_e):
        return

    epis = [r for r in epis if r.get("validade_ca") is not None]
    if not colaboradores:
        st.info("Cadastre ou reative um colaborador antes de registrar uma entrega.")
    elif not epis:
        st.info("Cadastre um EPI ativo com CA válido antes de registrar uma entrega.")
    else:
        mapa_c = {f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r for r in colaboradores}
        mapa_e = {f"{r['nome']} · CA {r['ca']} · {r['unidade']}": r for r in epis}

        with st.form("sst_form_entrega"):
            colab_label = st.selectbox("Colaborador", list(mapa_c))
            st.markdown("**Itens da entrega**")
            e1, q1 = st.columns([4, 1])
            epi1 = e1.selectbox("EPI 1", list(mapa_e), key="sst_epi1")
            qtd1 = q1.number_input("Qtd. 1", 1, 1000, 1, 1)

            adicionar2 = st.checkbox("Adicionar segundo EPI")
            epi2 = qtd2 = None
            if adicionar2:
                e2, q2 = st.columns([4, 1])
                epi2 = e2.selectbox("EPI 2", list(mapa_e), key="sst_epi2")
                qtd2 = q2.number_input("Qtd. 2", 1, 1000, 1, 1)

            adicionar3 = st.checkbox("Adicionar terceiro EPI")
            epi3 = qtd3 = None
            if adicionar3:
                e3, q3 = st.columns([4, 1])
                epi3 = e3.selectbox("EPI 3", list(mapa_e), key="sst_epi3")
                qtd3 = q3.number_input("Qtd. 3", 1, 1000, 1, 1)

            observacao = st.text_area("Observação (opcional)", max_chars=2000)
            enviado = st.form_submit_button("Registrar entrega", use_container_width=True)

        if enviado:
            colab = mapa_c[colab_label]
            selecoes = [(epi1, qtd1)]
            if adicionar2:
                selecoes.append((epi2, qtd2))
            if adicionar3:
                selecoes.append((epi3, qtd3))
            itens = [{"epi_id": int(mapa_e[e]["id"]), "quantidade": int(q)} for e, q in selecoes]
            resumo = [("Colaborador", colab["nome"])]
            for i, (e, q) in enumerate(selecoes, 1):
                resumo.append((f"EPI {i}", f"{e} · Quantidade {q}"))
            _confirmar_acao(
                "Entrega de EPI",
                resumo,
                lambda: registrar_entrega_epi(actor, int(colab["id"]), itens, observacao),
                "Entrega #{resultado} registrada com sucesso. O comprovante foi criado em Documentos / OS de SST.",
            )

    ok, entregas = _executar(listar_entregas)
    if ok:
        st.divider()
        st.markdown("#### Histórico de entregas")
        _tabela_historico_entregas(entregas)


def _render_documentos(actor: dict) -> None:
    st.subheader("Documentos / Ordens de Serviço de SST")

    ok_c, colaboradores = _executar(listar_colaboradores, apenas_ativos=True)
    if ok_c and colaboradores:
        mapa_c = {f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r for r in colaboradores}
        with st.expander("➕ Criar documento / OS de SST"):
            with st.form("sst_form_documento"):
                colab_label = st.selectbox("Colaborador", list(mapa_c))
                tipo = st.selectbox("Tipo", TIPOS_DOCUMENTO)
                motivo = st.text_input("Motivo (opcional)")
                titulo = st.text_input("Título")
                conteudo = st.text_area("Conteúdo / orientações", height=180, max_chars=20000)
                enviado = st.form_submit_button("Criar documento", use_container_width=True)
            if enviado:
                colab = mapa_c[colab_label]
                _confirmar_acao(
                    "Criação de documento SST",
                    [("Colaborador", colab["nome"]), ("Tipo", tipo), ("Título", titulo)],
                    lambda: criar_documento_sst(actor, int(colab["id"]), tipo, motivo, titulo, conteudo),
                    "Documento criado com sucesso.",
                )

    ok, documentos = _executar(listar_documentos)
    if not ok:
        return
    if not documentos:
        st.info("Nenhum documento SST criado.")
        return

    tabela = [{
        "Número": r["numero"],
        "Data": _data_hora(r["criado_em"]),
        "Colaborador": r["colaborador"],
        "Tipo": r["tipo"],
        "Título": r["titulo"],
        "Status": r["status"],
    } for r in documentos]
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    rascunhos = [r for r in documentos if r["status"] == "Rascunho"]
    if rascunhos:
        with st.expander("📄 Gerar PDF e fechar para assinatura"):
            mapa = {f"{r['numero']} · {r['colaborador']} · {r['titulo']}": r for r in rascunhos}
            escolha = st.selectbox("Documento", list(mapa), key="sst_fechar_doc")
            alvo = mapa[escolha]
            if st.button("Gerar PDF e fechar", type="primary", use_container_width=True):
                ok_doc, doc = _executar(obter_documento, int(alvo["id"]))
                if ok_doc:
                    pdf = gerar_pdf_documento(doc)
                    nome = f"{doc['numero']}_{doc['tipo'].replace(' ', '_').replace('/', '-')}.pdf"
                    _confirmar_acao(
                        "Fechar documento para assinatura",
                        [("Documento", doc["numero"]), ("Colaborador", doc["colaborador"]), ("Título", doc["titulo"])],
                        lambda: fechar_documento_para_assinatura(actor, int(doc["id"]), pdf, nome),
                        "Documento fechado para assinatura. Hash SHA-256 registrado.",
                    )

    fechados = [r for r in documentos if r["status"] in ("Aguardando Assinatura", "Assinado") and r.get("nome_arquivo")]
    if fechados:
        with st.expander("⬇️ Baixar PDF fechado"):
            mapa = {f"{r['numero']} · {r['colaborador']} · {r['status']}": r for r in fechados}
            escolha = st.selectbox("PDF", list(mapa), key="sst_download_doc")
            alvo = mapa[escolha]
            ok_pdf, dados = _executar(obter_pdf_documento, int(alvo["id"]))
            if ok_pdf:
                pdf, nome, hash_doc = dados
                st.caption(f"SHA-256: {hash_doc}")
                st.download_button(
                    "Baixar PDF",
                    data=pdf,
                    file_name=nome,
                    mime="application/pdf",
                    use_container_width=True,
                    on_click="ignore",
                )


def _render_assinaturas() -> None:
    st.subheader("Assinaturas")
    st.warning(
        "A integração com o leitor biométrico ainda não está habilitada. "
        "O sistema já prepara e preserva o PDF exato e seu hash, mas não simula uma biometria."
    )
    ok, pendentes = _executar(listar_pendentes_assinatura)
    if ok and pendentes:
        st.markdown("#### Aguardando assinatura biométrica")
        tabela = [{
            "Número": r["numero"],
            "Colaborador": r["colaborador"],
            "Matrícula": r.get("matricula") or "—",
            "Tipo": r["tipo"],
            "Título": r["titulo"],
            "Fechado em": _data_hora(r["fechado_em"]),
        } for r in pendentes]
        st.dataframe(tabela, use_container_width=True, hide_index=True)
    elif ok:
        st.info("Nenhum documento aguardando assinatura.")



def _render_dashboard(actor: dict) -> None:
    st.markdown("### Visão geral")
    st.caption("Resumo operacional do módulo SST/EPI.")

    ok_c, colaboradores = _executar(listar_colaboradores, apenas_ativos=False)
    ok_e, epis = _executar(listar_epis, apenas_ativos=False)
    ok_ent, entregas = _executar(listar_entregas)
    ok_doc, documentos = _executar(listar_documentos)
    ok_ass, pendentes = _executar(listar_pendentes_assinatura)
    if not all((ok_c, ok_e, ok_ent, ok_doc, ok_ass)):
        return

    hoje = datetime.now(TZ_BAHIA).date()
    ativos = sum(1 for r in colaboradores if r.get("ativo"))
    epis_ativos = sum(1 for r in epis if r.get("ativo"))
    ca_proximos = sum(
        1 for r in epis
        if r.get("ativo") and r.get("validade_ca") and 0 <= (r["validade_ca"] - hoje).days <= 30
    )
    limite = datetime.now(TZ_BAHIA) - timedelta(days=30)
    entregas_30 = 0
    for r in entregas:
        data = r.get("entregue_em")
        if data:
            try:
                if data.astimezone(TZ_BAHIA) >= limite:
                    entregas_30 += 1
            except Exception:
                pass

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Colaboradores ativos", ativos)
    m2.metric("EPIs ativos", epis_ativos)
    m3.metric("CA vencendo em 30 dias", ca_proximos)
    m4.metric("Entregas em 30 dias", entregas_30)
    m5.metric("Aguardando assinatura", len(pendentes))

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        renderizar_card_texto(
            "Controle de EPI",
            "O CA é validado para novas entregas e o histórico preserva o CA e a validade existentes no momento da entrega.",
        )
    with c2:
        renderizar_card_texto(
            "Documentos e assinatura",
            "Documentos fechados preservam o PDF exato e o hash SHA-256, preparando o fluxo para integração biométrica real.",
        )

    st.markdown("#### Situação dos documentos")
    if documentos:
        contagem = {}
        for r in documentos:
            status = r.get("status") or "Sem status"
            contagem[status] = contagem.get(status, 0) + 1
        st.dataframe(
            [{"Status": k, "Quantidade": v} for k, v in sorted(contagem.items())],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum documento SST criado ainda.")

def renderizar_modulo_sst(actor: dict) -> None:
    aplicar_estilo_sst()
    inicializar_banco_sst()

    if mensagem := st.session_state.pop("sst_mensagem", None):
        mostrar_notificacao(mensagem)

    renderizar_cabecalho_modulo()

    opcoes = {
        "📊 Visão geral": _render_dashboard,
        "👷 Colaboradores": _render_colaboradores,
        "⛑️ EPIs": _render_epis,
        "📦 Entrega de EPI": _render_entregas,
        "📄 Documentos / OS de SST": _render_documentos,
        "✍️ Assinaturas": lambda _actor: _render_assinaturas(),
    }
    escolha = st.radio(
        "Módulo",
        list(opcoes),
        horizontal=True,
        label_visibility="collapsed",
        key="sst_aba_ativa",
    )
    opcoes[escolha](actor)
