"""Unit tests for cryptographic utilities (password hashing)."""

from __future__ import annotations

import pytest

from sqlstack.lib.crypt import get_encryption_key, get_password_hash, verify_password


class TestPasswordHashing:
    """Test password hashing and verification with Argon2."""

    async def test_hash_password_returns_different_hashes(self) -> None:
        """Same password should produce different hashes due to salt."""
        password = "SecurePassword123!"

        hash1 = await get_password_hash(password)
        hash2 = await get_password_hash(password)

        assert hash1 != hash2, "Same password should produce different hashes (salted)"
        assert len(hash1) > 0, "Hash should not be empty"
        assert len(hash2) > 0, "Hash should not be empty"
        assert hash1.startswith("$argon2"), "Hash should be Argon2 format"
        assert hash2.startswith("$argon2"), "Hash should be Argon2 format"

    async def test_verify_password_correct(self) -> None:
        """Correct password should verify successfully."""
        password = "SecurePassword123!"
        hashed = await get_password_hash(password)

        result = await verify_password(password, hashed)

        assert result is True, "Correct password should verify"

    async def test_verify_password_incorrect(self) -> None:
        """Incorrect password should not verify."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = await get_password_hash(password)

        result = await verify_password(wrong_password, hashed)

        assert result is False, "Incorrect password should not verify"

    async def test_hash_password_string_input(self) -> None:
        """Test hashing with string password."""
        password = "TestPassword123!"

        hashed = await get_password_hash(password)

        assert isinstance(hashed, str), "Hash should be string"
        assert len(hashed) > 0, "Hash should not be empty"
        assert hashed.startswith("$argon2"), "Hash should be Argon2 format"

    async def test_hash_password_bytes_input(self) -> None:
        """Test hashing with bytes password."""
        password_bytes = b"TestPassword123!"

        hashed = await get_password_hash(password_bytes)

        assert isinstance(hashed, str), "Hash should be string"
        assert len(hashed) > 0, "Hash should not be empty"
        assert hashed.startswith("$argon2"), "Hash should be Argon2 format"

    async def test_verify_password_string_and_bytes(self) -> None:
        """Test verification works with both string and bytes."""
        password_str = "TestPassword123!"
        password_bytes = b"TestPassword123!"

        # Hash with string, verify with string
        hash_from_str = await get_password_hash(password_str)
        assert await verify_password(password_str, hash_from_str) is True

        # Hash with bytes, verify with bytes
        hash_from_bytes = await get_password_hash(password_bytes)
        assert await verify_password(password_bytes, hash_from_bytes) is True

        # Hash with string, verify with bytes
        assert await verify_password(password_bytes, hash_from_str) is True

        # Hash with bytes, verify with string
        assert await verify_password(password_str, hash_from_bytes) is True

    async def test_hash_password_empty_string(self) -> None:
        """Test hashing empty password (should work but not recommended)."""
        password = ""

        hashed = await get_password_hash(password)

        assert isinstance(hashed, str), "Should return hash even for empty string"
        assert len(hashed) > 0, "Hash should not be empty"

        # Verify empty password
        result = await verify_password("", hashed)
        assert result is True, "Empty password should verify against its hash"

    async def test_hash_password_very_long(self) -> None:
        """Test hashing very long password (1000+ chars)."""
        password = "A" * 1000 + "123!@#"

        hashed = await get_password_hash(password)

        assert isinstance(hashed, str), "Should handle very long passwords"
        assert len(hashed) > 0, "Hash should not be empty"

        # Verify long password
        result = await verify_password(password, hashed)
        assert result is True, "Long password should verify"

    async def test_verify_password_invalid_hash_format(self) -> None:
        """Test verification with invalid hash format."""
        from pwdlib.exceptions import UnknownHashError

        password = "TestPassword123!"
        invalid_hash = "not-a-valid-hash"

        # pwdlib raises UnknownHashError for invalid hashes
        with pytest.raises(UnknownHashError):
            await verify_password(password, invalid_hash)

    async def test_hash_password_special_characters(self) -> None:
        """Test hashing passwords with special characters."""
        special_passwords = [
            "Password!@#$%^&*()",
            "\u041f\u0430\u0440\u043e\u043b\u044c123!",  # Unicode (Cyrillic)
            "密码123!",  # Unicode (Chinese)
            "🔒Password123!",  # Emoji
            "Pass\nword123!",  # Newline
            "Pass\tword123!",  # Tab
        ]

        for password in special_passwords:
            hashed = await get_password_hash(password)
            assert isinstance(hashed, str), f"Should hash special password: {password!r}"
            assert await verify_password(password, hashed) is True, f"Should verify: {password!r}"

    async def test_verify_password_empty_hash(self) -> None:
        """Test verification with empty hash."""
        from pwdlib.exceptions import UnknownHashError

        password = "TestPassword123!"

        # pwdlib raises UnknownHashError for empty/invalid hashes
        with pytest.raises(UnknownHashError):
            await verify_password(password, "")

    async def test_hash_password_consistency(self) -> None:
        """Test that same password hashed multiple times can all verify."""
        password = "ConsistentPassword123!"
        hashes = []

        # Generate 5 different hashes
        for _ in range(5):
            hashed = await get_password_hash(password)
            hashes.append(hashed)

        # All hashes should be different
        assert len(set(hashes)) == 5, "All hashes should be unique"

        # All hashes should verify the same password
        for hashed in hashes:
            result = await verify_password(password, hashed)
            assert result is True, "All hashes should verify the same password"

    async def test_verify_password_case_sensitive(self) -> None:
        """Test that password verification is case-sensitive."""
        password = "TestPassword123!"
        wrong_case = "testpassword123!"
        hashed = await get_password_hash(password)

        assert await verify_password(password, hashed) is True
        assert await verify_password(wrong_case, hashed) is False, "Should be case-sensitive"

    async def test_hash_password_whitespace_matters(self) -> None:
        """Test that whitespace in passwords matters."""
        password1 = "Password123!"
        password2 = " Password123!"  # Leading space
        password3 = "Password123! "  # Trailing space

        hash1 = await get_password_hash(password1)

        # Different passwords should not verify
        assert await verify_password(password1, hash1) is True
        assert await verify_password(password2, hash1) is False
        assert await verify_password(password3, hash1) is False


class TestEncryptionKey:
    """Test encryption key generation."""

    def test_get_encryption_key_basic(self) -> None:
        """Test basic encryption key generation."""
        secret = "my-secret-key"

        key = get_encryption_key(secret)

        assert isinstance(key, bytes), "Key should be bytes"
        assert len(key) > 0, "Key should not be empty"

    def test_get_encryption_key_short_secret(self) -> None:
        """Test encryption key with short secret (padded to 32 chars)."""
        secret = "short"

        key = get_encryption_key(secret)

        assert isinstance(key, bytes), "Key should be bytes"
        # Should be padded to 32 bytes then base64 encoded
        assert len(key) > 0, "Key should not be empty"

    def test_get_encryption_key_exact_32_chars(self) -> None:
        """Test encryption key with exactly 32 character secret."""
        secret = "a" * 32

        key = get_encryption_key(secret)

        assert isinstance(key, bytes), "Key should be bytes"
        assert len(key) > 0, "Key should not be empty"

    def test_get_encryption_key_long_secret(self) -> None:
        """Test encryption key with long secret (>32 chars)."""
        secret = "a" * 64

        key = get_encryption_key(secret)

        assert isinstance(key, bytes), "Key should be bytes"
        # Should be truncated to 32 bytes then base64 encoded
        assert len(key) > 0, "Key should not be empty"

    def test_get_encryption_key_consistency(self) -> None:
        """Test that same secret produces same key."""
        secret = "consistent-secret"

        key1 = get_encryption_key(secret)
        key2 = get_encryption_key(secret)

        assert key1 == key2, "Same secret should produce same key"

    def test_get_encryption_key_different_secrets(self) -> None:
        """Test that different secrets produce different keys."""
        secret1 = "secret-one"
        secret2 = "secret-two"

        key1 = get_encryption_key(secret1)
        key2 = get_encryption_key(secret2)

        assert key1 != key2, "Different secrets should produce different keys"

    def test_get_encryption_key_url_safe_base64(self) -> None:
        """Test that key is URL-safe base64 encoded."""
        secret = "my-secret-key"

        key = get_encryption_key(secret)

        # URL-safe base64 uses - and _ instead of + and /
        assert b"+" not in key, "Should not contain + (URL-safe)"
        assert b"/" not in key, "Should not contain / (URL-safe)"

    def test_get_encryption_key_empty_secret(self) -> None:
        """Test encryption key with empty secret."""
        secret = ""

        key = get_encryption_key(secret)

        assert isinstance(key, bytes), "Should handle empty secret"
        assert len(key) > 0, "Key should not be empty"

    def test_get_encryption_key_special_characters(self) -> None:
        """Test encryption key with special characters in secret."""
        secrets = [
            "secret!@#$%^&*()",
            "secret\nwith\nnewlines",
            "secret\twith\ttabs",
            "secret with spaces",
        ]

        for secret in secrets:
            key = get_encryption_key(secret)
            assert isinstance(key, bytes), f"Should handle: {secret!r}"
            assert len(key) > 0, f"Key should not be empty for: {secret!r}"
