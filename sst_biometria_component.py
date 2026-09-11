from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).with_name("sst_biometria_component_frontend")
_biometria_component = components.declare_component(
    "copa_sst_biometria_bridge",
    path=str(_COMPONENT_DIR),
)


def executar_agente_biometrico(
    *,
    acao: str,
    payload: dict[str, Any] | None = None,
    request_id: str,
    agent_url: str = "http://127.0.0.1:8765",
    key: str | None = None,
):
    """Executa no navegador uma chamada ao agente biométrico local.

    A chamada precisa ocorrer no navegador do usuário porque o Streamlit roda na
    nuvem e não consegue acessar o USB/localhost da estação Windows.
    """
    if acao not in {"health", "cadastro", "verificacao"}:
        raise ValueError("Ação biométrica inválida.")

    return _biometria_component(
        acao=acao,
        payload=payload or {},
        request_id=str(request_id),
        agent_url=str(agent_url).rstrip("/"),
        default=None,
        key=key or f"sst_bio_{acao}_{request_id}",
    )
