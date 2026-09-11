"""Tests for verify_token's dual signing-mode support (2026-09-11).

Supabase issues HS256-signed tokens on the legacy shared-secret setting, but
ES256/RS256-signed tokens (verified via JWKS, not the shared secret) on
projects using the newer "JWT Signing Keys" feature. Before this fix,
verify_token only ever tried HS256 with SUPABASE_JWT_SECRET, so any
ES256/RS256 token was rejected with "The specified alg value is not
allowed" — not a bad secret, just the wrong verification method entirely.
"""

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

import app.core.security as security
from app.core.config import settings


@pytest.mark.asyncio
async def test_hs256_token_still_verifies_via_shared_secret() -> None:
    token = jwt.encode(
        {"sub": "user-hs256", "email": "hs256@example.com"},
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    payload = security.verify_token(token)
    assert payload["sub"] == "user-hs256"


@pytest.mark.asyncio
async def test_es256_token_verifies_via_jwks_not_shared_secret(monkeypatch) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    token = jwt.encode(
        {"sub": "user-es256", "email": "es256@example.com"},
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key-1"},
    )

    class _FakeSigningKey:
        key = public_key

    class _FakeJWKClient:
        def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
            return _FakeSigningKey()

    monkeypatch.setattr(security, "_get_jwks_client", lambda: _FakeJWKClient())

    payload = security.verify_token(token)
    assert payload["sub"] == "user-es256"


@pytest.mark.asyncio
async def test_es256_token_rejected_before_the_fix_would_have_said_alg_not_allowed(monkeypatch) -> None:
    """Regression guard: confirms the failure mode this fix addresses is
    actually gone, not just that the happy path works. Forcing the old
    HS256-only behavior back reproduces the exact reported error.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": "user-es256"}, private_key, algorithm="ES256")

    with pytest.raises(jwt.exceptions.InvalidAlgorithmError):
        jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
