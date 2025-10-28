"""Unit tests for type annotations."""

from __future__ import annotations

import msgspec


class TestTypeAnnotations:
    """Test custom type annotations work correctly."""

    def test_email_type_import(self) -> None:
        """Test Email type can be imported."""
        from sqlstack.lib.types import Email

        assert Email is not None
        # Verify it's an Annotated type with metadata
        assert hasattr(Email, "__metadata__"), "Email should be Annotated type"

    def test_password_type_import(self) -> None:
        """Test Password type can be imported."""
        from sqlstack.lib.types import Password

        assert Password is not None
        assert hasattr(Password, "__metadata__"), "Password should be Annotated type"

    def test_name_type_import(self) -> None:
        """Test Name type can be imported."""
        from sqlstack.lib.types import Name

        assert Name is not None
        assert hasattr(Name, "__metadata__"), "Name should be Annotated type"

    def test_username_type_import(self) -> None:
        """Test Username type can be imported."""
        from sqlstack.lib.types import Username

        assert Username is not None
        assert hasattr(Username, "__metadata__"), "Username should be Annotated type"

    def test_url_type_import(self) -> None:
        """Test Url type can be imported."""
        from sqlstack.lib.types import Url

        assert Url is not None
        assert hasattr(Url, "__metadata__"), "Url should be Annotated type"

    def test_slug_type_import(self) -> None:
        """Test Slug type can be imported."""
        from sqlstack.lib.types import Slug

        assert Slug is not None
        assert hasattr(Slug, "__metadata__"), "Slug should be Annotated type"

    def test_phone_type_import(self) -> None:
        """Test Phone type can be imported."""
        from sqlstack.lib.types import Phone

        assert Phone is not None
        assert hasattr(Phone, "__metadata__"), "Phone should be Annotated type"

    def test_all_exports(self) -> None:
        """Test that __all__ contains all expected types."""
        from sqlstack.lib import types

        expected_types = ["Email", "Password", "Name", "Username", "Url", "Slug", "Phone"]

        assert hasattr(types, "__all__"), "Module should have __all__"
        assert set(types.__all__) == set(expected_types), "Should export all type aliases"

    def test_email_metadata(self) -> None:
        """Test Email type has correct metadata."""
        from sqlstack.lib.types import Email

        # Extract metadata
        metadata = Email.__metadata__
        assert len(metadata) > 0, "Should have metadata"

        # Check for Meta with description
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta), "Should be msgspec.Meta"
        assert meta.description == "Valid email address", "Should have correct description"

    def test_password_metadata(self) -> None:
        """Test Password type has correct metadata."""
        from sqlstack.lib.types import Password

        metadata = Password.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "password" in meta.description.lower(), "Should mention password"
        assert "12+" in meta.description, "Should mention length requirement"

    def test_name_metadata(self) -> None:
        """Test Name type has correct metadata."""
        from sqlstack.lib.types import Name

        metadata = Name.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "name" in meta.description.lower(), "Should describe name"

    def test_username_metadata(self) -> None:
        """Test Username type has correct metadata."""
        from sqlstack.lib.types import Username

        metadata = Username.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "username" in meta.description.lower(), "Should describe username"

    def test_url_metadata(self) -> None:
        """Test Url type has correct metadata."""
        from sqlstack.lib.types import Url

        metadata = Url.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "url" in meta.description.lower() or "http" in meta.description.lower()

    def test_slug_metadata(self) -> None:
        """Test Slug type has correct metadata."""
        from sqlstack.lib.types import Slug

        metadata = Slug.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "slug" in meta.description.lower(), "Should describe slug"

    def test_phone_metadata(self) -> None:
        """Test Phone type has correct metadata."""
        from sqlstack.lib.types import Phone

        metadata = Phone.__metadata__
        meta = metadata[0]
        assert isinstance(meta, msgspec.Meta)
        assert "phone" in meta.description.lower(), "Should describe phone"

    def test_types_are_string_based(self) -> None:
        """Test that all types are based on str."""
        from sqlstack.lib.types import Email, Name, Password, Phone, Slug, Url, Username

        # All should be Annotated[str, ...]
        for type_alias in [Email, Password, Name, Username, Url, Slug, Phone]:
            # Get the origin type (should be str)
            import typing

            args = typing.get_args(type_alias)
            assert args[0] is str, f"{type_alias} should be based on str"
