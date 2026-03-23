"""Tests for auth module."""
import pytest

from agentend.auth.jwt import encode_token, verify_token, TokenPayload


class TestJWT:
    """Test JWT token operations."""

    def test_create_and_verify_token(self):
        token = encode_token(
            user_id="user-123",
            tenant_id="tenant-456",
            roles=["admin", "user"],
            capabilities=["invoice_processing"],
            secret="test-secret",
        )
        assert isinstance(token, str)
        assert len(token) > 0

        decoded = verify_token(token, secret="test-secret")
        assert decoded.user_id == "user-123"
        assert decoded.tenant_id == "tenant-456"
        assert "admin" in decoded.roles

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            verify_token("invalid.token.here", secret="test-secret")

    def test_wrong_secret_raises(self):
        token = encode_token(
            user_id="u1", tenant_id="t1", roles=[], capabilities=[], secret="secret-a"
        )
        with pytest.raises(Exception):
            verify_token(token, secret="secret-b")
