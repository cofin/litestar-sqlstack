"""Transactional email services and template rendering stubs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from litestar_email import EmailService


class TemplateRenderer:
    """Stub TemplateRenderer for email formatting."""

    def __init__(self) -> None:
        pass


class EmailMessageService:
    """Stub EmailMessageService to send emails using litestar_email."""

    def __init__(self, email_service: EmailService) -> None:
        self.email_service = email_service
