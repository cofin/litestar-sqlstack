"""Semantic type aliases with msgspec.Meta validation constraints.

These types provide both documentation and automatic structural validation
when used with msgspec decoding. For business logic validation (blocked
domains, common passwords, etc.), use the corresponding validators in
``sqlstack.utils.validation``.

Example:
    >>> import msgspec
    >>> from sqlstack.utils.types import Email
    >>>
    >>> # Structural validation happens automatically during decode
    >>> msgspec.json.decode(b'"user@example.com"', type=Email)
    'user@example.com'
    >>>
    >>> # Too short - fails structural validation
    >>> msgspec.json.decode(b'"a"', type=Email)
    msgspec.ValidationError: Expected `str` of length >= 3
"""

from typing import Annotated

import msgspec

__all__ = ("Email", "Name", "Password", "Slug", "Url", "Username")

# Email: RFC 5321 limits (254 total, 64 local part)
# Pattern validates basic structure; use validate_email() for blocked domains
Email = Annotated[
    str,
    msgspec.Meta(
        min_length=3,
        max_length=254,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        description="Valid email address",
    ),
]

# Password: 12-128 chars, structural only
# Use validate_password() for strength requirements (uppercase, digits, symbols, etc.)
Password = Annotated[
    str,
    msgspec.Meta(
        min_length=12, max_length=128, description="Strong password (12+ chars, mixed case, numbers, symbols)"
    ),
]

# Name: 1-100 chars, Unicode-friendly
# Use validate_name() for additional character and pattern validation
Name = Annotated[str, msgspec.Meta(min_length=1, max_length=100, description="Human name (1-100 characters)")]

# Username: 3-30 chars, lowercase alphanumeric with hyphens/underscores
# Must start with letter or number
# Use validate_username() for reserved username checks
Username = Annotated[
    str,
    msgspec.Meta(
        min_length=3,
        max_length=30,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Username (3-30 chars, alphanumeric/hyphens/underscores)",
    ),
]

# URL: Max 2048 chars, must start with http:// or https://
# Use validate_url() for blocked domains and security checks
Url = Annotated[str, msgspec.Meta(max_length=2048, pattern=r"^https?://", description="Valid HTTP/HTTPS URL")]

# Slug: 1-100 chars, lowercase alphanumeric with hyphens (no consecutive/leading/trailing)
# Use validate_slug() for additional hyphen rules
Slug = Annotated[
    str,
    msgspec.Meta(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe slug (lowercase, alphanumeric, hyphens)",
    ),
]
