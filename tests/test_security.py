from security import hash_senha, verificar_senha, validar_senha_forte, usuario_valido


def test_argon2_roundtrip():
    h = hash_senha("SenhaForte123")
    assert h.startswith("$argon2")
    assert verificar_senha("SenhaForte123", h)[0] is True
    assert verificar_senha("errada", h)[0] is False


def test_senha_forte():
    assert validar_senha_forte("SenhaForte123")[0]
    assert not validar_senha_forte("fraca123")[0]


def test_usuario_valido():
    assert usuario_valido("joao.silva")
    assert not usuario_valido("a")
    assert not usuario_valido("joao silva")
