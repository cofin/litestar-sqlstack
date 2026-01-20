"""Unit tests for type annotations."""

from __future__ import annotations

import typing

import msgspec


class TestTypeAnnotations:
    """Test custom type annotations work correctly."""

    def test_email_type_import(self) -> None:
        """Test Email type can be imported."""
        from sqlstack.utils.types import Email

        assert Email is not None
        # Verify it's an Annotated type with metadata
        assert hasattr(Email, "__metadata__"), "Email should be Annotated type"

    def test_password_type_import(self) -> None:
        """Test Password type can be imported."""
        from sqlstack.utils.types import Password

        assert Password is not None
        assert hasattr(Password, "__metadata__"), "Password should be Annotated type"

    def test_name_type_import(self) -> None:
        """Test Name type can be imported."""
        from sqlstack.utils.types import Name

        assert Name is not None
        assert hasattr(Name, "__metadata__"), "Name should be Annotated type"

    def test_username_type_import(self) -> None:
        """Test Username type can be imported."""
        from sqlstack.utils.types import Username

        assert Username is not None
        assert hasattr(Username, "__metadata__"), "Username should be Annotated type"

    def test_url_type_import(self) -> None:
        """Test Url type can be imported."""
        from sqlstack.utils.types import Url

        assert Url is not None
        assert hasattr(Url, "__metadata__"), "Url should be Annotated type"

    def test_slug_type_import(self) -> None:
        """Test Slug type can be imported."""
        from sqlstack.utils.types import Slug

        assert Slug is not None
        assert hasattr(Slug, "__metadata__"), "Slug should be Annotated type"

    def test_all_exports(self) -> None:
        """Test that __all__ contains all expected types."""
        from sqlstack.utils import types

        expected_types = ["Email", "Password", "Name", "Username", "Url", "Slug"]

        assert hasattr(types, "__all__"), "Module should have __all__"
        assert set(types.__all__) == set(expected_types), "Should export all type aliases"

    def test_email_metadata(self) -> None:
        """Test Email type has correct metadata with constraints."""
        from sqlstack.utils.types import Email

        metadata = Email.__metadata__
        assert len(metadata) > 0, "Should have metadata"

        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta), "Should be msgspec.Meta"
        assert meta.description == "Valid email address", "Should have correct description"
        assert meta.min_length == 3, "Should have min_length constraint"
        assert meta.max_length == 254, "Should have max_length constraint"
        assert meta.pattern is not None, "Should have pattern constraint"

    def test_password_metadata(self) -> None:
        """Test Password type has correct metadata with constraints."""
        from sqlstack.utils.types import Password

        metadata = Password.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "password" in meta.description.lower(), "Should mention password"
        assert meta.min_length == 12, "Should have min_length constraint"
        assert meta.max_length == 128, "Should have max_length constraint"

    def test_name_metadata(self) -> None:
        """Test Name type has correct metadata with constraints."""
        from sqlstack.utils.types import Name

        metadata = Name.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "name" in meta.description.lower(), "Should describe name"
        assert meta.min_length == 1, "Should have min_length constraint"
        assert meta.max_length == 100, "Should have max_length constraint"

    def test_username_metadata(self) -> None:
        """Test Username type has correct metadata with constraints."""
        from sqlstack.utils.types import Username

        metadata = Username.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "username" in meta.description.lower(), "Should describe username"
        assert meta.min_length == 3, "Should have min_length constraint"
        assert meta.max_length == 30, "Should have max_length constraint"
        assert meta.pattern is not None, "Should have pattern constraint"

    def test_url_metadata(self) -> None:
        """Test Url type has correct metadata with constraints."""
        from sqlstack.utils.types import Url

        metadata = Url.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "url" in meta.description.lower() or "http" in meta.description.lower()
        assert meta.max_length == 2048, "Should have max_length constraint"
        assert meta.pattern is not None, "Should have pattern constraint"

    def test_slug_metadata(self) -> None:
        """Test Slug type has correct metadata with constraints."""
        from sqlstack.utils.types import Slug

        metadata = Slug.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "slug" in meta.description.lower(), "Should describe slug"
        assert meta.min_length == 1, "Should have min_length constraint"
        assert meta.max_length == 100, "Should have max_length constraint"
        assert meta.pattern is not None, "Should have pattern constraint"

    def test_types_are_string_based(self) -> None:
        """Test that all types are based on str."""
        from sqlstack.utils.types import Email, Name, Password, Slug, Url, Username

        # All should be Annotated[str, ...]
        for type_alias in [Email, Password, Name, Username, Url, Slug]:
            args = typing.get_args(type_alias)
            assert args[0] is str, f"{type_alias} should be based on str"

    def test_email_structural_validation(self) -> None:
        """Test Email type enforces structural constraints via msgspec."""
        from sqlstack.utils.types import Email

        # Valid emails should decode successfully
        valid_email = msgspec.json.decode(b'"user@example.com"', type=Email)
        assert valid_email == "user@example.com"

    def test_password_structural_validation(self) -> None:
        """Test Password type enforces length constraints via msgspec."""
        import pytest

        from sqlstack.utils.types import Password

        # Too short password should fail
        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'"short"', type=Password)

        # Valid length password should decode
        valid_pwd = msgspec.json.decode(b'"ValidP@ssword123"', type=Password)
        assert valid_pwd == "ValidP@ssword123"

    def test_username_structural_validation(self) -> None:
        """Test Username type enforces pattern constraints via msgspec."""
        import pytest

        from sqlstack.utils.types import Username

        # Too short username should fail
        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'"ab"', type=Username)

        # Valid username should decode
        valid_user = msgspec.json.decode(b'"valid_user123"', type=Username)
        assert valid_user == "valid_user123"
