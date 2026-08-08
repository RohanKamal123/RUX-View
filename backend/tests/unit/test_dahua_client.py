"""Tests for backend/core/p2p/dahua_client.py -- EXPERIMENTAL, unverified
against real Dahua hardware (see that module's docstring). Only
compute_login_hash() is a pure function with no network/protocol
uncertainty, so it's the only piece with meaningful unit coverage here.
"""

import hashlib

from backend.core.p2p.dahua_client import compute_login_hash


def test_compute_login_hash_matches_documented_formula():
    """Per the dh-p2p project's documented auth formula:
    MD5(f"{username}:Login to {randsalt}:{password}")."""
    expected = hashlib.md5(b"admin:Login to abc123:hunter2").hexdigest()
    assert compute_login_hash("admin", "hunter2", "abc123") == expected


def test_compute_login_hash_is_deterministic():
    a = compute_login_hash("admin", "pw", "salt1")
    b = compute_login_hash("admin", "pw", "salt1")
    assert a == b


def test_compute_login_hash_differs_with_different_salt():
    a = compute_login_hash("admin", "pw", "salt1")
    b = compute_login_hash("admin", "pw", "salt2")
    assert a != b
