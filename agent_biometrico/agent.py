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

from sst_biometria_protocol import PROTOCOL_VERSION, gerar_hmac

HOST = "127.0.0.1"
PORT = int(os.getenv("SST_BIOMETRIC_AGENT_PORT", "8765"))
AGENT_ID = os.getenv("SST_BIOMETRIC_AGENT_ID", "copa-sst-windows-agent")
STATION_NAME = os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "estacao-local"
ALLOWED_ORIGIN = os.getenv("SST_BIOMETRIC_ALLOWED_ORIGIN", "").strip().rstrip("/")

# Deve ser exatamente o mesmo identificador aceito hoje pelo backend SST.
BACKEND_READER_MODEL = "Nitgen Hamster DX HFDU06"


class SdkNaoConfigurado(RuntimeError):
    pass


def _sdk_adapter():
    """Carrega o SDK real. Sem ele cadastro/verificação permanecem bloqueados."""
    try:
        from vendor_nitgen import NitgenAdapter  # type: ignore
        return NitgenAdapter()
    except Exception as exc:
        raise SdkNaoConfigurado("SDK Nitgen/eNBioBSP não configurado nesta estação.") from exc


def _secret() -> str:
    value = os.getenv("SST_BIOMETRIC_AGENT_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("SST_BIOMETRIC_AGENT_SECRET deve possuir pelo menos 32 caracteres.")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _origin_allowed(origin: str | None) -> bool:
    if not ALLOWED_ORIGIN:
        return origin in (None, "", "null")
    return str(origin or "").rstrip("/") == ALLOWED_ORIGIN


class Handler(BaseHTTPRequestHandler):
    server_version = "CopaSSTBiometricAgent/0.2"

    def log_message(self, fmt: str, *args) -> None:
        # Não registra payloads biométricos.
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if ALLOWED_ORIGIN and _origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Copa-Agent-Request")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _blocked_origin(self) -> bool:
        if _origin_allowed(self.headers.get("Origin")):
            return False
        self._send(403, {"ok": False, "erro": "ORIGIN_NOT_ALLOWED"})
        return True

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not 0 < length <= 16_384:
            raise ValueError("Payload inválido.")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Payload inválido.")
        return data

    def do_OPTIONS(self) -> None:
        if self._blocked_origin():
            return
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self._blocked_origin():
            return
        if self.path != "/health":
            self._send(404, {"ok": False, "erro": "NOT_FOUND"})
            return
        try:
            adapter = _sdk_adapter()
            sdk_ok, sdk_version = True, adapter.sdk_version()
        except Exception:
            sdk_ok, sdk_version = False, None
        self._send(200, {
            "ok": True,
            "agente_id": AGENT_ID,
            "estacao": STATION_NAME,
            "protocolo_versao": PROTOCOL_VERSION,
            "modelo_leitor": BACKEND_READER_MODEL,
            "sdk_configurado": sdk_ok,
            "sdk_versao": sdk_version,
            "timestamp": _now_iso(),
        })

    def do_POST(self) -> None:
        if self._blocked_origin():
            return
        if self.headers.get("X-Copa-Agent-Request") != "1":
            self._send(400, {"ok": False, "erro": "INVALID_REQUEST"})
            return
        if self.path not in {"/cadastro", "/verificacao"}:
            self._send(404, {"ok": False, "erro": "NOT_FOUND"})
            return

        try:
            payload, adapter, segredo = self._read_json(), _sdk_adapter(), _secret()
        except SdkNaoConfigurado as exc:
            self._send(503, {"ok": False, "erro": "SDK_NOT_CONFIGURED", "mensagem": str(exc)})
            return
        except Exception as exc:
            self._send(400, {"ok": False, "erro": "CONFIG_OR_REQUEST_ERROR", "mensagem": str(exc)})
            return

        try:
            if self.path == "/cadastro":
                colaborador_id = int(payload["colaborador_id"])
                result = adapter.enroll(colaborador_id=colaborador_id)
                evidencia = {
                    "protocolo_versao": PROTOCOL_VERSION,
                    "evento_id": secrets.token_urlsafe(24),
                    "tipo_evento": "cadastro",
                    "timestamp": _now_iso(),
                    "agente_id": AGENT_ID,
                    "estacao": STATION_NAME,
                    "dispositivo_modelo": BACKEND_READER_MODEL,
                    "dispositivo_serial": result.get("dispositivo_serial"),
                    "sdk_versao": result.get("sdk_versao"),
                    "referencia_biometrica": result["referencia_biometrica"],
                    "template_hash": result.get("template_hash"),
                    "resultado": "CADASTRADO",
                    "score_verificacao": None,
                    "colaborador_id": colaborador_id,
                }
            else:
                colaborador_id = int(payload["colaborador_id"])
                documento_id = int(payload["documento_id"])
                hash_documento = str(payload["hash_documento"]).strip().lower()
                referencia = str(payload["referencia_biometrica"]).strip()
                result = adapter.verify(colaborador_id=colaborador_id, referencia_biometrica=referencia)
                if result.get("validado") is not True:
                    self._send(401, {"ok": False, "erro": "BIOMETRIA_NAO_CONFIRMADA"})
                    return
                evidencia = {
                    "protocolo_versao": PROTOCOL_VERSION,
                    "evento_id": secrets.token_urlsafe(24),
                    "tipo_evento": "verificacao",
                    "timestamp": _now_iso(),
                    "agente_id": AGENT_ID,
                    "estacao": STATION_NAME,
                    "dispositivo_modelo": BACKEND_READER_MODEL,
                    "dispositivo_serial": result.get("dispositivo_serial"),
                    "sdk_versao": result.get("sdk_versao"),
                    "referencia_biometrica": referencia,
                    "template_hash": None,
                    "resultado": "VALIDADO",
                    "score_verificacao": result.get("score_verificacao"),
                    "colaborador_id": colaborador_id,
                    "documento_id": documento_id,
                    "hash_documento": hash_documento,
                }

            evidencia["assinatura_hmac"] = gerar_hmac(evidencia, segredo)
            self._send(200, {"ok": True, "evidencia": evidencia})
        except Exception as exc:
            self._send(500, {"ok": False, "erro": "AGENT_ERROR", "mensagem": str(exc)})


def main() -> None:
    _secret()  # falha fechada caso o segredo não esteja configurado
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Copa SST Biometric Agent em http://{HOST}:{PORT}")
    print(f"Origem autorizada: {ALLOWED_ORIGIN or '(configuração local)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
