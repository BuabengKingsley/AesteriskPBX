import hashlib
import hmac
import secrets


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def verify_secret(value: str, digest: str, secret_key: str) -> bool:
    return hmac.compare_digest(hash_secret(value, secret_key), digest)

