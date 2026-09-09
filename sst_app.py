"""
Interface inicial do módulo SST / EPI.

Este arquivo é propositalmente separado do app.py principal.
Ele poderá ser importado pelo sistema matriz quando o módulo estiver pronto
para testes integrados.
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
)


def _executar(funcao, *args, **kwargs):
    try:
        resultado = funcao(*args, **kwargs)
        return True, resultado
    except Exception as exc:
        st.error(str(exc))
        return False, None


def renderizar_modulo_sst(actor: dict) -> None:
    """Renderiza a interface inicial do módulo SST/EPI."""
    inicializar_banco_sst()

    st.title("🦺 SST / EPI")
    st.caption("Gestão de colaboradores, EPIs, entregas e documentos de Segurança do Trabalho.")

    aba_colab, aba_epi, aba_entrega, aba_docs, aba_ass = st.tabs(
        [
            "👷 Colaboradores",
            "🦺 EPIs",
            "📦 Entrega de EPI",
            "📄 Documentos / OS de SST",
            "✍️ Assinaturas",
        ]
    )

    with aba_colab:
        st.subheader("Colaboradores")
        with st.expander("➕ Cadastrar colaborador"):
            with st.form("sst_form_colaborador", clear_on_submit=True):
                nome = st.text_input("Nome completo")
                cpf = st.text_input("CPF")
                matricula = st.text_input("Matrícula")
                funcao = st.text_input("Função")
                setor = st.text_input("Setor")
                enviado = st.form_submit_button("Cadastrar colaborador", use_container_width=True)

            if enviado:
                ok, _ = _executar(
                    cadastrar_colaborador,
                    actor,
                    nome=nome,
                    cpf=cpf,
                    matricula=matricula,
                    funcao=funcao,
                    setor=setor,
                )
                if ok:
                    st.success("Colaborador cadastrado com sucesso.")
                    st.rerun()

        ok, colaboradores = _executar(listar_colaboradores, apenas_ativos=True)
        if ok:
            if colaboradores:
                st.dataframe(colaboradores, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum colaborador cadastrado.")

    with aba_epi:
        st.subheader("EPIs")
        with st.expander("➕ Cadastrar EPI"):
            with st.form("sst_form_epi", clear_on_submit=True):
                nome_epi = st.text_input("EPI")
                ca = st.text_input("CA")
                fabricante = st.text_input("Fabricante")
                unidade = st.text_input("Unidade", value="un")
                enviado_epi = st.form_submit_button("Cadastrar EPI", use_container_width=True)

            if enviado_epi:
                ok, _ = _executar(
                    cadastrar_epi,
                    actor,
                    nome=nome_epi,
                    ca=ca,
                    fabricante=fabricante,
                    unidade=unidade,
                )
                if ok:
                    st.success("EPI cadastrado com sucesso.")
                    st.rerun()

        ok, epis = _executar(listar_epis, apenas_ativos=True)
        if ok:
            if epis:
                st.dataframe(epis, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum EPI cadastrado.")

    with aba_entrega:
        st.subheader("Entrega de EPI")
        st.info(
            "A tela operacional de entrega será habilitada na próxima etapa, "
            "após validarmos os cadastros de colaboradores e EPIs."
        )
        ok, entregas = _executar(listar_entregas)
        if ok and entregas:
            st.dataframe(entregas, use_container_width=True, hide_index=True)

    with aba_docs:
        st.subheader("Documentos / Ordens de Serviço de SST")
        st.info(
            "Aqui serão geradas as OS de SST de admissão, mudança de função, "
            "revisões e outros documentos de ciência."
        )
        ok, documentos = _executar(listar_documentos)
        if ok and documentos:
            st.dataframe(documentos, use_container_width=True, hide_index=True)

    with aba_ass:
        st.subheader("Assinaturas")
        st.warning(
            "Integração biométrica ainda não habilitada. "
            "A assinatura só será ativada após definição e teste do leitor/SDK."
        )
        st.markdown(
            """
            A futura validação registrará, entre outras evidências:

            - colaborador identificado;
            - documento e versão;
            - hash de integridade;
            - data e hora;
            - estação/equipamento;
            - resultado da validação biométrica.
            """
        )
