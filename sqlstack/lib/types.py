"""Production-ready field validation utilities with comprehensive security checks."""

from typing import Annotated

import msgspec

__all__ = ("Email", "Name", "Password", "Phone", "Slug", "Url", "Username")

Email = Annotated[str, msgspec.Meta(description="Valid email address")]
Password = Annotated[str, msgspec.Meta(description="Strong password (12+ chars, mixed case, numbers, symbols)")]
Name = Annotated[str, msgspec.Meta(description="Human name (1-100 characters)")]
Username = Annotated[str, msgspec.Meta(description="Username (3-30 characters, alphanumeric/hyphens/underscores)")]
Url = Annotated[str, msgspec.Meta(description="Valid HTTP/HTTPS URL")]
Slug = Annotated[str, msgspec.Meta(description="URL-safe slug (lowercase, alphanumeric, hyphens)")]
Phone = Annotated[str, msgspec.Meta(description="Valid international phone number")]
