"""Tests for backend/core/crypto.py -- symmetric encryption for secrets
stored at rest (camera P2P passwords)."""

from unittest.mock import patch

from backend.core.crypto import decrypt_secret, encrypt_secret


def test_encrypt_then_decrypt_round_trips():
    token = encrypt_secret("super-secret-password")
    assert token != "super-secret-password"
    assert decrypt_secret(token) == "super-secret-password"


def test_encrypt_empty_string_returns_empty():
    assert encrypt_secret("") == ""


def test_decrypt_empty_string_returns_empty():
    assert decrypt_secret("") == ""


def test_decrypt_garbage_returns_empty_not_raises():
    assert decrypt_secret("not-a-real-token") == ""


def test_decrypt_with_wrong_key_returns_empty_not_raises():
    with patch("backend.core.crypto.settings") as mock_settings:
        mock_settings.secret_key = "key-one"
        token = encrypt_secret("hello")

    with patch("backend.core.crypto.settings") as mock_settings:
        mock_settings.secret_key = "key-two"
        assert decrypt_secret(token) == ""


def test_encrypted_output_is_not_deterministic_but_both_decrypt():
    """Fernet includes a random IV/timestamp, so encrypting the same
    plaintext twice must produce different tokens -- both must still
    decrypt to the same value."""
    token_a = encrypt_secret("same-password")
    token_b = encrypt_secret("same-password")
    assert token_a != token_b
    assert decrypt_secret(token_a) == "same-password"
    assert decrypt_secret(token_b) == "same-password"
