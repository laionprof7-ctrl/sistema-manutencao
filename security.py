import hashlib
import hmac
import re
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_senha(senha: str) -> str:
    return _PH.hash(senha)


def verificar_senha(senha: str, armazenada: str) -> tuple[bool, bool]:
    """Retorna (senha_valida, precisa_upgrade). Suporta hashes legados."""
    if not armazenada:
        return False, False

    if armazenada.startswith("$argon2"):
        try:
            valido = _PH.verify(armazenada, senha)
            return bool(valido), bool(_PH.check_needs_rehash(armazenada))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False, False

    if armazenada.startswith("pbkdf2_sha256$"):
        try:
            _, iteracoes, salt_hex, digest_hex = armazenada.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes)
            )
            return hmac.compare_digest(digest.hex(), digest_hex), True
        except (ValueError, TypeError):
            return False, False

    if re.fullmatch(r"[0-9a-fA-F]{64}", armazenada):
        legado = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legado, armazenada.lower()), True

    return False, False


def validar_senha_forte(senha: str) -> tuple[bool, str]:
    if len(senha) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    if len(senha) > 128:
        return False, "A senha é longa demais."
    if not re.search(r"[A-Z]", senha):
        return False, "Inclua pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", senha):
        return False, "Inclua pelo menos uma letra minúscula."
    if not re.search(r"\d", senha):
        return False, "Inclua pelo menos um número."
    return True, ""


def normalizar_usuario(valor: str) -> str:
    return (valor or "").strip().lower()


def usuario_valido(valor: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9._-]{3,40}", normalizar_usuario(valor)))
