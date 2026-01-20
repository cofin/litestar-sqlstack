"""Portal utilities for async context management.

This module re-exports portal utilities from sqlspec for managing
async context across sync/async boundaries.
"""

from sqlspec.utils.portal import Portal

__all__ = ["Portal"]
