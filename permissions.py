NIVEL_MOTORISTA = 1.0
NIVEL_OPERACIONAL = 2.0
NIVEL_COORDENADOR = 3.0
NIVEL_COORDENADOR_PLUS = 3.5
NIVEL_ADMIN = 4.0


def pode_ver_oficina(nivel: float) -> bool:
    return nivel == NIVEL_OPERACIONAL or nivel >= NIVEL_ADMIN


def pode_triagem(nivel: float) -> bool:
    return nivel >= NIVEL_COORDENADOR


def pode_gerir_usuarios(nivel: float) -> bool:
    return nivel >= NIVEL_COORDENADOR_PLUS


def pode_gerir_os(nivel: float) -> bool:
    return nivel >= NIVEL_ADMIN


def pode_editar_usuario(nivel_editor: float, nivel_alvo: float) -> bool:
    return nivel_editor >= NIVEL_COORDENADOR_PLUS and nivel_editor > nivel_alvo and nivel_alvo < NIVEL_ADMIN


def pode_conceder_nivel(nivel_editor: float, novo_nivel: float) -> bool:
    return novo_nivel < NIVEL_ADMIN and novo_nivel < nivel_editor
