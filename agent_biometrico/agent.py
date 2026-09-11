from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sst_biometria_protocol import PROTOCOL_VERSION, READER_MODEL, gerar_hmac

HOST = "127.0.0.1"
PORT = int(os.getenv("SST_BIOMETRIC_AGENT_PORT", "8765"))
AGENT_ID = os.getenv("SST_BIOMETRIC_AGENT_ID", "copa-sst-windows-agent")
STATION_NAME = os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "estacao-local"
ALLOWED_ORIGIN = os.getenv("SST_BIOMETRIC_ALLOWED_ORIGIN", "").strip().rstrip("/")


class SdkNaoConfigurado(RuntimeError):
    pass


def _sdk_adapter():
    """Carrega o adaptador real somente quando o SDK Nitgen estiver instalado.

    O arquivo vendor_nitgen.py NÃO faz parte do scaffold porque depende do SDK
    proprietário instalado na estação Windows. Sem ele, cadastro/verificação
    permanecem bloqueados e nunca retornam sucesso simulado.
    """
    try:
        from vendor_nitgen import NitgenAdapter  # type: ignore
    except Exception as exc:
        raise SdkNaoConfigurado(
            "SDK Nitgen/eNBioBSP não configurado nesta estação."
        ) from exc
    return NitgenAdapter()


def _secret() -> str:
    value = os.getenv("SST_BIOMETRIC_AGENT_SECRET", "").strip()
    if not value:
        raise RuntimeError("SST_BIOMETRIC_AGENT_SECRET não configurado no agente local.")
    if len(value) < 32:
        raise RuntimeError("SST_BIOMETRIC_AGENT_SECRET deve possuir pelo menos 32 caracteres.")
    return value


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_origin(origin: str | None) -> bool:
    if not ALLOWED_ORIGIN:
        return origin in (None, "", "null")
    return str(origin or "").rstrip("/") == ALLOWED_ORIGIN


class Handler(BaseHTTPRequestHandler):
    server_version = "CopaSSTBiometricAgent/0.1"

    def log_message(self, fmt: str, *args) -> None:
        # Evita despejar payloads biométricos no terminal. Registra só método/caminho/status.
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if ALLOWED_ORIGIN and _safe_origin(origin):
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Copa-Agent-Request")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reject_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if _safe_origin(origin):
            return False
        self._send(403, {"ok": False, "erro": "ORIGIN_NOT_ALLOWED"})
        return True

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 16_384:
            raise ValueError("Payload inválido.")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Payload inválido.")
        return data

    def do_OPTIONS(self) -> None:
        if self._reject_origin():
            return
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self._reject_origin():
            return
        if self.path != "/health":
            self._send(404, {"ok": False, "erro": "NOT_FOUND"})
            return

        sdk_ok = True
        sdk_versao = None
        try:
            adapter = _sdk_adapter()
            sdk_versao = adapter.sdk_version()
        except Exception:
            sdk_ok = False

        self._send(200, {
            "ok": True,
            "agente_id": AGENT_ID,
            "estacao": STATION_NAME,
            "protocolo_versao": PROTOCOL_VERSION,
            "modelo_leitor": READER_MODEL,
            "sdk_configurado": sdk_ok,
            "sdk_versao": sdk_versao,
            "timestamp": _now_iso(),
        })

    def do_POST(self) -> None:
        if self._reject_origin():
            return
        if self.headers.get("X-Copa-Agent-Request") != "1":
            self._send(400, {"ok": False, "erro": "INVALID_REQUEST"})
            return

        if self.path not in {"/cadastro", "/verificacao"}:
            self._send(404, {"ok": False, "erro": "NOT_FOUND"})
            return

        try:
            payload = self._read_json()
            adapter = _sdk_adapter()
            segredo = _secret()
        except SdkNaoConfigurado as exc:
            self._send(503, {"ok": False, "erro": "SDK_NOT_CONFIGURED", "mensagem": str(exc)})
            return
        except Exception as exc:
            self._send(400, {"ok": False, "erro": "CONFIG_OR_REQUEST_ERROR", "mensagem": str(exc)})
            return

        try:
            if self.path == "/cadastro":
                colaborador_id = int(payload["colaborador_id"])
                resultado = adapter.enroll(colaborador_id=colaborador_id)
                evidencia = {
                    "protocolo_versao": PROTOCOL_VERSION,
                    "evento_id": secrets.token_urlsafe(24),
                    "tipo_evento": "cadastro",
                    "timestamp": _now_iso(),
                    "agente_id": AGENT_ID,
                    "estacao": STATION_NAME,
                    "dispositivo_modelo": READER_MODEL,
                    "dispositivo_serial": resultado.get("dispositivo_serial"),
                    "sdk_versao": resultado.get("sdk_versao"),
                    "referencia_biometrica": resultado["referencia_biometrica"],
                    "template_hash": resultado.get("template_hash"),
                    "resultado": "CADASTRADO",
                    "score_verificacao": None,
                    "colaborador_id": colaborador_id,
                }
            else:
                colaborador_id = int(payload["colaborador_id"])
                documento_id = int(payload["documento_id"])
                hash_documento = str(payload["hash_documento"]).strip().lower()
                referencia = str(payload["referencia_biometrica"]).strip()
                resultado = adapter.verify(
                    colaborador_id=colaborador_id,
                    referencia_biometrica=referencia,
                )
                if resultado.get("validado") is not True:
                    self._send(401, {"ok": False, "erro": "BIOMETRIA_NAO_CONFIRMADA"})
                    return
                evidencia = {
                    "protocolo_versao": PROTOCOL_VERSION,
                    "evento_id": secrets.token_urlsafe(24),
                    "tipo_evento": "verificacao",
                    "timestamp": _now_iso(),
                    "agente_id": AGENT_ID,
                    "estacao": STATION_NAME,
                    "dispositivo_modelo": READER_MODEL,
                    "dispositivo_serial": resultado.get("dispositivo_serial"),
                    "sdk_versao": resultado.get("sdk_versao"),
                    "referencia_biometrica": referencia,
                    "template_hash": None,
                    "resultado": "VALIDADO",
                    "score_verificacao": resultado.get("score_verificacao"),
                    "colaborador_id": colaborador_id,
                    "documento_id": documento_id,
                    "hash_documento": hash_documento,
                }

            # Nunca incluir imagem/template bruto na resposta.
            evidencia["assinatura_hmac"] = gerar_hmac(evidencia, segredo)
            self._send(200, {"ok": True, "evidencia": evidencia})
        except Exception as exc:
            self._send(500, {"ok": False, "erro": "AGENT_ERROR", "mensagem": str(exc)})


def main() -> None:
    # Valida segredo já na subida; falha fechada em vez de iniciar inseguro.
    _secret()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Copa SST Biometric Agent ouvindo somente em http://{HOST}:{PORT}")
    print(f"Origem autorizada: {ALLOWED_ORIGIN or '(somente chamadas sem Origin durante configuração local)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
