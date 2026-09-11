from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

PROTOCOL_VERSION = "1"
READER_MODEL = "Nitgen/FingerTech Hamster DX HFDU06"
MAX_EVIDENCE_AGE_SECONDS = 120

# Campos que nunca devem viajar do agente local para o backend do SST.
FORBIDDEN_BIOMETRIC_FIELDS = {
    "imagem",
    "image",
    "fingerprint_image",
    "fingerprint_image_b64",
    "raw_image",
    "template",
    "template_b64",
    "template_bytes",
}


class BiometriaProtocolError(ValueError):
    """Evidência biométrica inválida, incompleta ou incompatível com o documento."""


@dataclass(frozen=True)
class EvidenciaBiometrica:
    evento_id: str
    colaborador_id: int
    documento_id: int
    hash_documento: str
    referencia_biometrica: str
    agente_id: str
    dispositivo_modelo: str
    dispositivo_serial: str | None
    sdk_versao: str | None
    score_verificacao: int | None
    capturado_em: datetime
    protocolo_versao: str = PROTOCOL_VERSION

    def para_registro(self) -> dict[str, Any]:
        return {
            "evento_id": self.evento_id,
            "colaborador_id": self.colaborador_id,
            "documento_id": self.documento_id,
            "hash_documento": self.hash_documento,
            "referencia_biometrica": self.referencia_biometrica,
            "agente_id": self.agente_id,
            "dispositivo_modelo": self.dispositivo_modelo,
            "dispositivo_serial": self.dispositivo_serial,
            "sdk_versao": self.sdk_versao,
            "score_verificacao": self.score_verificacao,
            "capturado_em": self.capturado_em,
            "protocolo_versao": self.protocolo_versao,
        }


def _texto(payload: Mapping[str, Any], campo: str, obrigatorio: bool = True) -> str | None:
    valor = payload.get(campo)
    texto = str(valor).strip() if valor is not None else ""
    if obrigatorio and not texto:
        raise BiometriaProtocolError(f"Campo obrigatório ausente na evidência biométrica: {campo}.")
    return texto or None


def _inteiro(payload: Mapping[str, Any], campo: str, obrigatorio: bool = True) -> int | None:
    valor = payload.get(campo)
    if valor in (None, ""):
        if obrigatorio:
            raise BiometriaProtocolError(f"Campo obrigatório ausente na evidência biométrica: {campo}.")
        return None
    try:
        return int(valor)
    except (TypeError, ValueError) as exc:
        raise BiometriaProtocolError(f"Campo inválido na evidência biométrica: {campo}.") from exc


def _instante_utc(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        instante = valor
    else:
        texto = str(valor or "").strip()
        if not texto:
            raise BiometriaProtocolError("Horário da leitura biométrica não informado.")
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"
        try:
            instante = datetime.fromisoformat(texto)
        except ValueError as exc:
            raise BiometriaProtocolError("Horário da leitura biométrica inválido.") from exc
    if instante.tzinfo is None:
        raise BiometriaProtocolError("Horário da leitura biométrica deve possuir fuso horário.")
    return instante.astimezone(timezone.utc)


def _hash_sha256_valido(valor: str) -> bool:
    return len(valor) == 64 and all(c in "0123456789abcdef" for c in valor.lower())


def _rejeitar_dados_biometricos_brutos(payload: Mapping[str, Any]) -> None:
    presentes = FORBIDDEN_BIOMETRIC_FIELDS.intersection({str(k).lower() for k in payload.keys()})
    if presentes:
        raise BiometriaProtocolError(
            "A evidência contém dado biométrico bruto proibido: " + ", ".join(sorted(presentes)) + "."
        )


def validar_evidencia(
    payload: Mapping[str, Any],
    *,
    colaborador_id_esperado: int,
    documento_id_esperado: int,
    hash_documento_esperado: str,
    agora: datetime | None = None,
    idade_maxima_segundos: int = MAX_EVIDENCE_AGE_SECONDS,
) -> EvidenciaBiometrica:
    """Valida a resposta do agente antes de permitir a assinatura do documento.

    A validação vincula a leitura ao colaborador e ao SHA-256 exato do PDF.
    Ela não valida o fabricante/SDK em si; essa responsabilidade é do agente local.
    """
    _rejeitar_dados_biometricos_brutos(payload)

    if payload.get("aprovado") is not True:
        raise BiometriaProtocolError("A identidade do colaborador não foi confirmada pela biometria.")

    versao = _texto(payload, "protocolo_versao")
    if versao != PROTOCOL_VERSION:
        raise BiometriaProtocolError("Versão do protocolo biométrico incompatível.")

    colaborador_id = _inteiro(payload, "colaborador_id")
    documento_id = _inteiro(payload, "documento_id")
    hash_documento = (_texto(payload, "hash_documento") or "").lower()

    if colaborador_id != int(colaborador_id_esperado):
        raise BiometriaProtocolError("A leitura biométrica pertence a outro colaborador.")
    if documento_id != int(documento_id_esperado):
        raise BiometriaProtocolError("A evidência biométrica pertence a outro documento.")
    if not _hash_sha256_valido(hash_documento):
        raise BiometriaProtocolError("SHA-256 inválido na evidência biométrica.")
    if not hmac.compare_digest(hash_documento, str(hash_documento_esperado).lower()):
        raise BiometriaProtocolError("O PDF confirmado pela biometria não é o documento atual.")

    capturado_em = _instante_utc(payload.get("capturado_em"))
    agora_utc = (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    idade = (agora_utc - capturado_em).total_seconds()
    if idade < -15:
        raise BiometriaProtocolError("Horário da estação biométrica está adiantado além do permitido.")
    if idade > int(idade_maxima_segundos):
        raise BiometriaProtocolError("A leitura biométrica expirou. Faça uma nova leitura.")

    score = _inteiro(payload, "score_verificacao", obrigatorio=False)
    if score is not None and score < 0:
        raise BiometriaProtocolError("Score biométrico inválido.")

    return EvidenciaBiometrica(
        evento_id=_texto(payload, "evento_id") or "",
        colaborador_id=colaborador_id,
        documento_id=documento_id,
        hash_documento=hash_documento,
        referencia_biometrica=_texto(payload, "referencia_biometrica") or "",
        agente_id=_texto(payload, "agente_id") or "",
        dispositivo_modelo=_texto(payload, "dispositivo_modelo") or "",
        dispositivo_serial=_texto(payload, "dispositivo_serial", obrigatorio=False),
        sdk_versao=_texto(payload, "sdk_versao", obrigatorio=False),
        score_verificacao=score,
        capturado_em=capturado_em,
        protocolo_versao=versao,
    )


def payload_canonico_para_assinatura(payload: Mapping[str, Any]) -> bytes:
    """Serialização estável usada pelo HMAC entre agente local e backend."""
    dados = {k: v for k, v in payload.items() if k != "assinatura_hmac"}
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def gerar_hmac(payload: Mapping[str, Any], segredo: str) -> str:
    if not segredo:
        raise BiometriaProtocolError("Segredo do agente biométrico não configurado.")
    return hmac.new(segredo.encode("utf-8"), payload_canonico_para_assinatura(payload), hashlib.sha256).hexdigest()


def verificar_hmac(payload: Mapping[str, Any], segredo: str) -> None:
    assinatura = str(payload.get("assinatura_hmac") or "").strip().lower()
    if not assinatura:
        raise BiometriaProtocolError("Evidência biométrica sem assinatura do agente.")
    esperado = gerar_hmac(payload, segredo)
    if not hmac.compare_digest(assinatura, esperado):
        raise BiometriaProtocolError("Assinatura do agente biométrico inválida.")
