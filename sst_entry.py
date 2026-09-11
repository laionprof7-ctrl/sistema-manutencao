from __future__ import annotations

# O menu SST fica leve: o core operacional e a biometria só são carregados
# quando o usuário realmente entra em uma área que precisa deles.
from sst_menu import renderizar_modulo_sst_menu as renderizar_modulo_sst

__all__ = ["renderizar_modulo_sst"]
