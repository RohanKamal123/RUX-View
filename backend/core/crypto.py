"""
crypto.py — Symmetric encryption for secrets stored at rest (camera P2P
passwords, etc).

Derives a Fernet key from settings.secret_key via SHA-256 so no separate
key management is required today. This is an interim solution -- a
dedicated KMS-managed key (e.g. GCP Secret Manager / Cloud KMS) would be
the production-grade upgrade, but this is a real improvement over storing
plaintext camera passwords, which is what the P2P/RTSP camera-credential
fields would otherwise do.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings


def _get_fernet() -> Fernet:
    key_material = (settings.secret_key or "dev-secret-key").encode("utf-8")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
    return Fernet(derived_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string for storage. Returns a token string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a token produced by encrypt_secret. Returns "" on any
    failure (wrong key, corrupted data) rather than raising -- callers use
    this for optional credentials, not security-critical auth tokens."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
