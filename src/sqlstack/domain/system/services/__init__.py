"""System domain services.

Provides services for system-level operations including background tasks.
"""

from sqlstack.domain.system.services._task import TaskService

__all__ = ("TaskService",)
