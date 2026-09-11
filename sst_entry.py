from __future__ import annotations

# Importa primeiro as extensões biométricas para que elas substituam as
# renderizações do core antes de o menu montar o mapa de áreas.
import sst_app  # noqa: F401

from sst_menu import renderizar_modulo_sst_menu as renderizar_modulo_sst

__all__ = ["renderizar_modulo_sst"]
