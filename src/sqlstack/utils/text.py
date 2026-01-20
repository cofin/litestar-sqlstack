"""Text processing utilities.

This module provides text transformation utilities including
slugification for generating URL-safe identifiers.

Re-exports from sqlspec.utils.text for convenience.
"""

from sqlspec.utils.text import slugify

__all__ = ["slugify"]
