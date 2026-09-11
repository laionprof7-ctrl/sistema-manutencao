from __future__ import annotations

import secrets

import streamlit as st

import sst_app_core as _core
from sst_biometria_component import executar_agente_biometrico
from sst_services import (
    obter_biometria_colaborador,
    registrar_assinatura_biometrica,
    registrar_cadastro_biometrico,
)

AGENT_URL = "http://127.0.0.1:8765"


def _novo_request_id(prefixo: str) -> str:
    return f"{prefixo}-{secrets.token_urlsafe(12)}"


def _status_agente(chave: str):
    request_id = st.session_state.setdefault(
        f"sst_bio_health_request_{chave}",
        _novo_request_id(f"health-{chave}"),
    )
    resultado = executar_agente_biometrico(
        acao="health",
        payload={},
        request_id=request_id,
        agent_url=AGENT_URL,
        key=f"sst_bio_health_component_{chave}",
    )

    if not resultado:
        st.caption("Verificando a estação biométrica…")
        return False, None

    if not resultado.get("bridge_ok"):
        st.error("Agente biométrico não encontrado nesta estação.")
        st.caption("Abra o agente Windows ou consulte ❓ Ajuda / Protocolos.")
        return False, resultado

    corpo = resultado.get("body") or {}
    if not resultado.get("ok"):
        st.error("O agente biométrico respondeu com erro.")
        return False, resultado

    if not corpo.get("sdk_configurado"):
        st.warning("Agente conectado. O leitor/SDK Nitgen ainda não está disponível nesta estação.")
        return False, resultado

    st.success("Leitor biométrico conectado e pronto.")
    return True, resultado


def _mostrar_epis_documento(doc: dict) -> None:
    if doc.get("tipo") != "Entrega de EPI":
        return
    try:
        import json
        snapshot = json.loads(doc.get("conteudo_snapshot") or "{}")
    except Exception:
        snapshot = {}

    itens = snapshot.get("itens") or []
    st.markdown("#### EPIs desta entrega")
    if itens:
        st.dataframe(
            [
                {
                    "EPI": item.get("nome") or "—",
                    "CA": item.get("ca") or "—",
                    "Quantidade": item.get("quantidade") or "—",
                    "Unidade": item.get("unidade") or "—",
                }
                for item in itens
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Não foi possível localizar os itens desta entrega no documento.")
    st.caption(f"Motivo da entrega: {snapshot.get('motivo_entrega') or doc.get('motivo') or '—'}")


def _processar_resultado_cadastro(actor: dict, colaborador_id: int, request_id: str) -> bool:
    resultado = executar_agente_biometrico(
        acao="cadastro",
        payload={"colaborador_id": colaborador_id},
        request_id=request_id,
        agent_url=AGENT_URL,
        key=f"sst_bio_enroll_component_{request_id}",
    )
    if not resultado:
        st.info("🖐️ Aguardando a captura da digital no leitor…")
        return False

    st.session_state.pop("sst_bio_enroll_request", None)
    if not resultado.get("bridge_ok"):
        st.session_state["sst_bio_last_error"] = "Não foi possível comunicar com o agente biométrico local."
        st.rerun()

    corpo = resultado.get("body") or {}
    if not resultado.get("ok") or not corpo.get("evidencia"):
        mensagem = corpo.get("mensagem") or corpo.get("erro") or "O cadastro biométrico não foi concluído."
        st.session_state["sst_bio_last_error"] = mensagem
        st.rerun()

    ok, _ = _core._executar(
        registrar_cadastro_biometrico,
        actor,
        colaborador_id,
        corpo["evidencia"],
    )
    if ok:
        st.session_state["sst_mensagem"] = "Biometria cadastrada com sucesso."
        st.session_state.pop("sst_bio_last_error", None)
        st.rerun()
    return False


def _render_cadastro_biometrico(actor: dict) -> None:
    st.divider()
    st.markdown("#### 🖐️ Cadastro biométrico")

    if erro := st.session_state.pop("sst_bio_last_error", None):
        st.error(erro)

    ok, colaboradores = _core._executar(_core._colaboradores_cache, True)
    if not ok or not colaboradores:
        st.info("Cadastre um colaborador ativo antes de cadastrar biometria.")
        return

    mapa = {
        f"{r['nome']} · Matrícula {r.get('matricula') or '—'}": r
        for r in colaboradores
    }
    escolha = st.selectbox(
        "Colaborador para biometria",
        list(mapa),
        key="sst_bio_cadastro_colaborador",
    )
    colaborador = mapa[escolha]
    colaborador_id = int(colaborador["id"])

    ok_bio, cadastro = _core._executar(obter_biometria_colaborador, colaborador_id)
    if ok_bio and cadastro and cadastro.get("ativo"):
        st.success("Este colaborador já possui biometria cadastrada.")
        rotulo = "Recadastrar biometria"
    else:
        st.warning("Biometria ainda não cadastrada.")
        rotulo = "Cadastrar biometria"

    pronto, _ = _status_agente(f"cadastro-{colaborador_id}")

    pendente = st.session_state.get("sst_bio_enroll_request")
    if pendente and int(pendente.get("colaborador_id", 0)) == colaborador_id:
        _processar_resultado_cadastro(actor, colaborador_id, pendente["request_id"])
        return

    if st.button(
        f"🖐️ {rotulo}",
        type="primary",
        use_container_width=True,
        disabled=not pronto,
        key=f"sst_bio_btn_cadastro_{colaborador_id}",
    ):
        st.session_state["sst_bio_enroll_request"] = {
            "colaborador_id": colaborador_id,
            "request_id": _novo_request_id(f"cadastro-{colaborador_id}"),
        }
        st.rerun()


_original_render_colaboradores = _core._render_colaboradores


def _render_colaboradores_com_biometria(actor: dict) -> None:
    _original_render_colaboradores(actor)
    _render_cadastro_biometrico(actor)


@st.dialog("Confirmação biométrica", width="large")
def _popup_assinatura_biometrica(selecionado: dict) -> None:
    st.markdown("### 🖐️ Confirme a identidade do colaborador")
    st.caption("A pessoa que está recebendo o material deve conferir os itens e colocar o dedo no leitor.")

    ok_doc, doc = _core._executar(_core.obter_documento, int(selecionado["id"]))
    if not ok_doc or not doc:
        return

    colaborador_id = int(doc["colaborador_id"])
    documento_id = int(doc["id"])

    c1, c2 = st.columns(2)
    c1.write(f"**Colaborador:** {doc['colaborador']}")
    c1.write(f"**Matrícula:** {doc.get('matricula') or '—'}")
    c2.write(f"**Documento:** {doc['numero']}")
    c2.write(f"**Tipo:** {doc['tipo']}")

    _mostrar_epis_documento(doc)

    ok_bio, cadastro = _core._executar(obter_biometria_colaborador, colaborador_id)
    possui_biometria = bool(ok_bio and cadastro and cadastro.get("ativo"))

    if possui_biometria:
        st.success("Biometria cadastrada para este colaborador.")
    else:
        st.warning("Biometria ainda não cadastrada. Faça o cadastro na área Colaboradores.")

    pronto, _ = _status_agente(f"assinatura-{documento_id}")

    if erro := st.session_state.pop("sst_bio_sign_error", None):
        st.error(erro)

    pendente = st.session_state.get("sst_bio_sign_request")
    if pendente and int(pendente.get("documento_id", 0)) == documento_id:
        resultado = executar_agente_biometrico(
            acao="verificacao",
            payload={
                "colaborador_id": colaborador_id,
                "documento_id": documento_id,
                "hash_documento": doc.get("hash_documento") or "",
                "referencia_biometrica": cadastro.get("referencia_biometrica") if cadastro else "",
            },
            request_id=pendente["request_id"],
            agent_url=AGENT_URL,
            key=f"sst_bio_verify_component_{pendente['request_id']}",
        )

        if not resultado:
            st.info("🖐️ Aguardando a leitura da digital…")
        else:
            st.session_state.pop("sst_bio_sign_request", None)
            if not resultado.get("bridge_ok"):
                st.session_state["sst_bio_sign_error"] = "Não foi possível comunicar com o agente biométrico local."
                st.rerun()

            corpo = resultado.get("body") or {}
            if not resultado.get("ok") or not corpo.get("evidencia"):
                st.session_state["sst_bio_sign_error"] = (
                    corpo.get("mensagem")
                    or corpo.get("erro")
                    or "A identidade não foi confirmada."
                )
                st.rerun()

            ok_ass, assinatura_id = _core._executar(
                registrar_assinatura_biometrica,
                st.session_state.get("user_info") or {},
                documento_id,
                colaborador_id,
                corpo["evidencia"],
            )
            if ok_ass:
                _core._limpar_caches_sst()
                st.session_state.pop("sst_assinatura_documento", None)
                st.session_state["sst_mensagem"] = (
                    f"Assinatura biométrica registrada com sucesso. Evidência #{assinatura_id}."
                )
                st.rerun()

    st.info("🖐️ Coloque o dedo no leitor quando solicitado.")

    c1, c2 = st.columns(2)
    if c1.button(
        "🖐️ Ler digital e confirmar identidade",
        type="primary",
        use_container_width=True,
        disabled=not (possui_biometria and pronto),
        key=f"sst_bio_confirmar_{documento_id}",
    ):
        st.session_state["sst_bio_sign_request"] = {
            "documento_id": documento_id,
            "request_id": _novo_request_id(f"verificacao-{documento_id}"),
        }
        st.rerun()

    if c2.button(
        "Cancelar",
        use_container_width=True,
        key=f"sst_cancelar_bio_{documento_id}",
    ):
        st.session_state.pop("sst_assinatura_documento", None)
        st.session_state.pop("sst_bio_sign_request", None)
        st.rerun()


_core._render_colaboradores = _render_colaboradores_com_biometria
_core._popup_assinatura_biometrica = _popup_assinatura_biometrica

renderizar_modulo_sst = _core.renderizar_modulo_sst
