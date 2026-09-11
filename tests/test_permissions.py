from permissions import (
    pode_conceder_nivel,
    pode_editar_usuario,
    pode_gerir_os,
    pode_gerir_usuarios,
    pode_triagem,
    pode_ver_oficina,
)


def test_permissoes_basicas():
    assert pode_ver_oficina(2.0)
    assert not pode_ver_oficina(3.0)
    assert pode_triagem(3.0)
    assert pode_gerir_usuarios(3.5)
    assert pode_gerir_os(4.0)


def test_hierarquia_usuario():
    assert pode_editar_usuario(4.0, 3.5)
    assert not pode_editar_usuario(3.5, 3.5)
    assert not pode_editar_usuario(4.0, 4.0)
    assert pode_conceder_nivel(4.0, 3.5)
    assert not pode_conceder_nivel(3.5, 3.5)
