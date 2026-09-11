from datetime import datetime, timedelta, timezone

import pytest

from sst_biometria_protocol import BiometriaProtocolError, gerar_hmac, validar_evidencia, verificar_hmac

HASH = "a" * 64


def payload_base(agora):
    return {
        "protocolo_versao": "1",
        "evento_id": "evt-123",
        "aprovado": True,
        "colaborador_id": 10,
        "documento_id": 20,
        "hash_documento": HASH,
        "referencia_biometrica": "ref-opaca-123",
        "agente_id": "estacao-almoxarifado-01",
        "dispositivo_modelo": "Nitgen/FingerTech Hamster DX HFDU06",
        "dispositivo_serial": "SERIAL-TESTE",
        "sdk_versao": "teste",
        "score_verificacao": 87,
        "capturado_em": agora.isoformat(),
    }


def test_evidencia_valida():
    agora = datetime.now(timezone.utc)
    ev = validar_evidencia(payload_base(agora), colaborador_id_esperado=10, documento_id_esperado=20, hash_documento_esperado=HASH, agora=agora)
    assert ev.evento_id == "evt-123"
    assert ev.hash_documento == HASH


def test_bloqueia_documento_diferente():
    agora = datetime.now(timezone.utc)
    payload = payload_base(agora)
    payload["hash_documento"] = "b" * 64
    with pytest.raises(BiometriaProtocolError, match="PDF confirmado"):
        validar_evidencia(payload, colaborador_id_esperado=10, documento_id_esperado=20, hash_documento_esperado=HASH, agora=agora)


def test_bloqueia_evidencia_expirada():
    agora = datetime.now(timezone.utc)
    payload = payload_base(agora - timedelta(minutes=5))
    with pytest.raises(BiometriaProtocolError, match="expirou"):
        validar_evidencia(payload, colaborador_id_esperado=10, documento_id_esperado=20, hash_documento_esperado=HASH, agora=agora)


def test_bloqueia_imagem_ou_template_bruto():
    agora = datetime.now(timezone.utc)
    payload = payload_base(agora)
    payload["fingerprint_image_b64"] = "nao-pode"
    with pytest.raises(BiometriaProtocolError, match="biométrico bruto"):
        validar_evidencia(payload, colaborador_id_esperado=10, documento_id_esperado=20, hash_documento_esperado=HASH, agora=agora)


def test_hmac_detecta_adulteracao():
    agora = datetime.now(timezone.utc)
    payload = payload_base(agora)
    payload["assinatura_hmac"] = gerar_hmac(payload, "segredo-teste")
    verificar_hmac(payload, "segredo-teste")
    payload["documento_id"] = 21
    with pytest.raises(BiometriaProtocolError, match="Assinatura do agente biométrico inválida"):
        verificar_hmac(payload, "segredo-teste")
