"""
Interface de desenvolvimento do módulo SST / EPI.
Separada do app.py principal até a validação do módulo.
"""

import streamlit as st

from sst_database import inicializar_banco_sst
from sst_services import (
    cadastrar_colaborador,
    cadastrar_epi,
    listar_colaboradores,
    listar_epis,
    listar_entregas,
    listar_documentos,
    registrar_entrega_epi,
)


UNIDADES_EPI = [
    "unidade",
    "par",
    "caixa",
    "pacote",
    "kit",
    "rolo",
    "frasco",
    "litro",
    "metro",
]


def _executar(operacao, *args, **kwargs):
    try:
        resultado = operacao(*args, **kwargs)
        return True, resultado
    except Exception as exc:
        st.error(str(exc))
        return False, None


@st.dialog("Confirmar cadastro do colaborador")
def _confirmar_colaborador(actor, dados):
    st.write("Confira os dados antes de salvar:")
    st.write(f"**Nome:** {dados['nome']}")
    st.write(f"**CPF:** {dados['cpf'] or '—'}")
    st.write(f"**Matrícula:** {dados['matricula'] or '—'}")
    st.write(f"**Função:** {dados['funcao']}")
    st.write(f"**Setor:** {dados['setor'] or '—'}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Confirmar cadastro", type="primary", use_container_width=True):
        ok, _ = _executar(cadastrar_colaborador, actor, **dados)
        if ok:
            st.session_state["sst_mensagem"] = "Colaborador cadastrado com sucesso."
            st.rerun()


@st.dialog("Confirmar cadastro do EPI")
def _confirmar_epi(actor, dados):
    st.write("Confira os dados antes de salvar:")
    st.write(f"**EPI:** {dados['nome']}")
    st.write(f"**CA:** {dados['ca'] or '—'}")
    st.write(f"**Validade do CA:** {dados['validade_ca'].strftime('%d/%m/%Y')}")
    st.write(f"**Fabricante:** {dados['fabricante'] or '—'}")
    st.write(f"**Unidade:** {dados['unidade']}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Confirmar cadastro", type="primary", use_container_width=True):
        ok, _ = _executar(cadastrar_epi, actor, **dados)
        if ok:
            st.session_state["sst_mensagem"] = "EPI cadastrado com sucesso."
            st.rerun()


@st.dialog("Confirmar entrega de EPI")
def _confirmar_entrega(actor, dados, colaborador_nome, epi_nome, unidade):
    st.warning("Confirme somente após conferir o colaborador e o EPI.")
    st.write(f"**Colaborador:** {colaborador_nome}")
    st.write(f"**EPI:** {epi_nome}")
    st.write(f"**Quantidade:** {dados['itens'][0]['quantidade']} {unidade}")
    st.write(f"**Observação:** {dados['observacao'] or '—'}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Confirmar entrega", type="primary", use_container_width=True):
        ok, entrega_id = _executar(registrar_entrega_epi, actor, **dados)
        if ok:
            st.session_state["sst_mensagem"] = f"Entrega #{entrega_id} registrada com sucesso."
            st.rerun()


def renderizar_modulo_sst(actor: dict) -> None:
    inicializar_banco_sst()

    if mensagem := st.session_state.pop("sst_mensagem", None):
        st.success(mensagem)

    st.title("🦺 SST / EPI")
    st.caption("Gestão de colaboradores, EPIs, entregas e documentos de Segurança do Trabalho.")

    aba_colab, aba_epi, aba_entrega, aba_docs, aba_ass = st.tabs(
        ["👷 Colaboradores", "🦺 EPIs", "📦 Entrega de EPI",
         "📄 Documentos / OS de SST", "✍️ Assinaturas"]
    )

    with aba_colab:
        st.subheader("Colaboradores")
        with st.expander("➕ Cadastrar colaborador"):
            with st.form("sst_form_colaborador"):
                nome = st.text_input("Nome completo")
                cpf = st.text_input("CPF")
                matricula = st.text_input("Matrícula")
                funcao = st.text_input("Função")
                setor = st.text_input("Setor")
                enviado = st.form_submit_button("Cadastrar colaborador", use_container_width=True)
            if enviado:
                if not nome.strip() or not funcao.strip():
                    st.error("Nome e função são obrigatórios.")
                else:
                    _confirmar_colaborador(actor, {
                        "nome": nome, "cpf": cpf, "matricula": matricula,
                        "funcao": funcao, "setor": setor,
                    })

        ok, colaboradores = _executar(listar_colaboradores, apenas_ativos=True)
        if ok:
            if colaboradores:
                st.dataframe(colaboradores, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum colaborador cadastrado.")

    with aba_epi:
        st.subheader("EPIs")
        with st.expander("➕ Cadastrar EPI"):
            with st.form("sst_form_epi"):
                nome_epi = st.text_input("EPI")
                ca = st.text_input("CA")
                validade_ca = st.date_input("Validade do CA", format="DD/MM/YYYY")
                fabricante = st.text_input("Fabricante")
                unidade = st.selectbox("Unidade", UNIDADES_EPI)
                enviado_epi = st.form_submit_button("Cadastrar EPI", use_container_width=True)
            if enviado_epi:
                if not nome_epi.strip() or not ca.strip():
                    st.error("EPI e CA são obrigatórios.")
                else:
                    _confirmar_epi(actor, {
                        "nome": nome_epi, "ca": ca, "fabricante": fabricante,
                        "unidade": unidade, "validade_ca": validade_ca,
                    })

        ok, epis = _executar(listar_epis, apenas_ativos=True)
        if ok:
            if epis:
                st.dataframe(epis, use_container_width=True, hide_index=True)
                st.caption("EPIs com CA vencido são desativados automaticamente e deixam de aparecer nas entregas.")
            else:
                st.info("Nenhum EPI ativo cadastrado.")

    with aba_entrega:
        st.subheader("Entrega de EPI")
        ok_c, colaboradores = _executar(listar_colaboradores, apenas_ativos=True)
        ok_e, epis = _executar(listar_epis, apenas_ativos=True)

        if ok_c and ok_e:
            if not colaboradores:
                st.info("Cadastre um colaborador ativo antes de registrar uma entrega.")
            elif not epis:
                st.info("Cadastre um EPI ativo e com CA válido antes de registrar uma entrega.")
            else:
                mapa_colab = {
                    f"{r['nome']} · Matrícula {r['matricula'] or '—'}": r
                    for r in colaboradores
                }
                mapa_epi = {
                    f"{r['nome']} · CA {r['ca'] or '—'} · {r['unidade']}": r
                    for r in epis
                }

                with st.form("sst_form_entrega"):
                    colab_label = st.selectbox("Colaborador", list(mapa_colab))
                    epi_label = st.selectbox("EPI", list(mapa_epi))
                    quantidade = st.number_input("Quantidade", min_value=1, max_value=1000, value=1, step=1)
                    observacao = st.text_area("Observação (opcional)", max_chars=2000)
                    enviado_entrega = st.form_submit_button("Registrar entrega", use_container_width=True)

                if enviado_entrega:
                    colab = mapa_colab[colab_label]
                    epi = mapa_epi[epi_label]
                    _confirmar_entrega(
                        actor,
                        {
                            "colaborador_id": int(colab["id"]),
                            "itens": [{"epi_id": int(epi["id"]), "quantidade": int(quantidade)}],
                            "observacao": observacao,
                        },
                        colab["nome"],
                        f"{epi['nome']} · CA {epi['ca'] or '—'}",
                        epi["unidade"],
                    )

        ok, entregas = _executar(listar_entregas)
        if ok:
            st.divider()
            st.markdown("#### Histórico de entregas")
            if entregas:
                linhas = []
                for r in entregas:
                    data = r["entregue_em"]
                    try:
                        data = data.astimezone().strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        data = str(data)

                    epi_ca = r["epi"]
                    if r.get("ca"):
                        epi_ca += f" · CA {r['ca']}"

                    linhas.append({
                        "Data": data,
                        "Colaborador": r["colaborador"],
                        "Matrícula": r.get("matricula") or "—",
                        "EPI / CA": epi_ca,
                        "Quantidade": r["quantidade"],
                    })

                st.dataframe(
                    linhas,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Data": st.column_config.TextColumn("Data"),
                        "Colaborador": st.column_config.TextColumn("Colaborador"),
                        "Matrícula": st.column_config.TextColumn("Matrícula"),
                        "EPI / CA": st.column_config.TextColumn("EPI / CA"),
                        "Quantidade": st.column_config.NumberColumn("Quantidade", format="%d"),
                    },
                )
            else:
                st.info("Nenhuma entrega registrada.")

    with aba_docs:
        st.subheader("Documentos / Ordens de Serviço de SST")
        st.info("Aqui serão geradas as OS de SST de admissão, mudança de função, revisões e outros documentos de ciência.")
        ok, documentos = _executar(listar_documentos)
        if ok and documentos:
            st.dataframe(documentos, use_container_width=True, hide_index=True)

    with aba_ass:
        st.subheader("Assinaturas")
        st.warning("Integração biométrica ainda não habilitada. A assinatura só será ativada após definição e teste do leitor/SDK.")
        st.markdown(
            "- colaborador identificado;\n"
            "- documento e versão;\n"
            "- hash de integridade;\n"
            "- data e hora;\n"
            "- estação/equipamento;\n"
            "- resultado da validação biométrica."
        )
