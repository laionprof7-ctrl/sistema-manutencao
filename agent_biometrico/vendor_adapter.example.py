"""Contrato do adaptador do SDK Nitgen.

Copie este arquivo para ``vendor_nitgen.py`` SOMENTE na estação Windows onde o
SDK oficial estiver instalado e implemente as chamadas reais do fabricante.

Este arquivo de exemplo nunca retorna sucesso simulado.
"""

from __future__ import annotations

from typing import Any


class NitgenAdapter:
    def __init__(self) -> None:
        raise RuntimeError(
            "Adaptador Nitgen ainda não implementado. Instale o SDK oficial e implemente vendor_nitgen.py."
        )

    def sdk_version(self) -> str:
        raise NotImplementedError

    def enroll(self, *, colaborador_id: int) -> dict[str, Any]:
        """Cadastrar a digital e devolver SOMENTE metadados seguros.

        Retorno esperado:
        {
            "referencia_biometrica": "identificador-opaco-no-agente",
            "template_hash": "sha256-do-template-se-o-sdk-permitir",
            "dispositivo_serial": "serial-do-leitor-ou-null",
            "sdk_versao": "versao-do-sdk"
        }

        Não devolva imagem ou template biométrico bruto.
        """
        raise NotImplementedError

    def verify(self, *, colaborador_id: int, referencia_biometrica: str) -> dict[str, Any]:
        """Executar uma correspondência REAL no leitor.

        Retorno esperado:
        {
            "validado": True/False,
            "score_verificacao": 0,
            "dispositivo_serial": "serial-do-leitor-ou-null",
            "sdk_versao": "versao-do-sdk"
        }

        O método deve retornar validado=True apenas se o SDK confirmar a identidade.
        """
        raise NotImplementedError
