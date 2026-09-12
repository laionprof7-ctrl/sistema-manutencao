from datetime import datetime, timezone

import pytest

import sst_services
from sst_services import RegraSSTError, _validar_evidencia_agente, registrar_cadastro_biometrico


def test_cadastro_biometrico_rejeita_evidencia_de_outro_colaborador(monkeypatch):
    monkeypatch.setattr(
        sst_services,
        "_validar_evidencia_agente",
        lambda *_: {
            "colaborador_id": 99,
            "resultado": "CADASTRADO",
            "dispositivo_modelo": sst_services.BIOMETRIA_MODELO_OFICIAL,
        },
    )

    with pytest.raises(RegraSSTError, match="outro colaborador"):
        registrar_cadastro_biometrico(
            {"usuario": "operador", "nivel": 3.0},
            colaborador_id=10,
            evidencia={},
        )


def test_score_biometrico_invalido_retorna_erro_controlado(monkeypatch):
    monkeypatch.setattr(sst_services, "_segredo_agente_biometrico", lambda: "x" * 32)
    evidencia = {
        "assinatura_hmac": "0" * 64,
        "evento_id": "evento",
        "protocolo_versao": "1",
        "tipo_evento": "cadastro",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "colaborador_id": 10,
        "score_verificacao": "não-numérico",
    }
    # O HMAC é validado antes do score; isolamos somente a conversão para
    # garantir que o erro exposto continue sendo uma regra controlada.
    monkeypatch.setattr(sst_services.hmac, "compare_digest", lambda *_: True)
    with pytest.raises(RegraSSTError, match="Score"):
        _validar_evidencia_agente(evidencia, "cadastro")


def test_falha_ao_excluir_storage_e_informada(monkeypatch):
    monkeypatch.setattr(
        sst_services,
        "_storage_requisicao",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("indisponível")),
    )

    assert sst_services._storage_excluir("documentos/teste.pdf") is False
