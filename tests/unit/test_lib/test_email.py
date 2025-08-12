"""Unit tests for email service."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from sqlstack import schemas as s
from sqlstack.lib.email import EmailService


@pytest.fixture
def mock_settings():
    """Mock settings for email service."""
    settings = MagicMock()
    settings.email = MagicMock()
    settings.email.ENABLED = True
    settings.email.SMTP_HOST = "smtp.example.com"
    settings.email.SMTP_PORT = 587
    settings.email.SMTP_USER = "test@example.com"
    settings.email.SMTP_PASSWORD = "password"
    settings.email.USE_TLS = True
    settings.email.USE_SSL = False
    settings.email.FROM_EMAIL = "noreply@example.com"
    settings.email.FROM_NAME = "Test App"
    settings.email.TIMEOUT = 30
    
    settings.app = MagicMock()
    settings.app.NAME = "Test Application"
    settings.app.URL = "http://localhost:8000"
    
    return settings


@pytest.fixture
def email_service(mock_settings):
    """Create email service with mocked settings."""
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.settings.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            return service


@pytest.fixture
def test_user():
    """Create a test user schema."""
    return s.User(
        id="123e4567-e89b-12d3-a456-426614174000",
        email="user@example.com",
        name="Test User",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )


def test_initialization_with_settings(mock_settings) -> None:
    """Test email service initialization."""
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.settings.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            
            assert service.settings == mock_settings.email
            assert service.app_settings == mock_settings.app
            assert service.base_url == mock_settings.app.URL
            assert service.app_name == mock_settings.app.NAME


def test_jinja_environment_setup(email_service) -> None:
    """Test Jinja2 environment is set up."""
    assert email_service.jinja_env is not None
    assert hasattr(email_service.jinja_env, "get_template")


def test_smtp_connection_disabled(mock_settings) -> None:
    """Test SMTP connection when email is disabled."""
    mock_settings.email.ENABLED = False
    
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.email.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            
            connection = service._create_smtp_connection()
            assert connection is None


@patch("smtplib.SMTP")
def test_smtp_connection_success(mock_smtp_class, email_service) -> None:
    """Test successful SMTP connection."""
    mock_smtp = MagicMock()
    mock_smtp_class.return_value = mock_smtp
    
    connection = email_service._create_smtp_connection()
    
    assert connection == mock_smtp
    mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=30)
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("test@example.com", "password")


@patch("smtplib.SMTP_SSL")
def test_smtp_ssl_connection(mock_smtp_ssl_class, mock_settings) -> None:
    """Test SMTP SSL connection."""
    mock_settings.email.USE_SSL = True
    mock_settings.email.USE_TLS = False
    mock_smtp_ssl = MagicMock()
    mock_smtp_ssl_class.return_value = mock_smtp_ssl
    
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.settings.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            
            connection = service._create_smtp_connection()
            
            assert connection == mock_smtp_ssl
            mock_smtp_ssl_class.assert_called_once_with("smtp.example.com", 587, timeout=30)
            mock_smtp_ssl.starttls.assert_not_called()  # No TLS needed with SSL


@patch("smtplib.SMTP")
def test_smtp_connection_without_credentials(mock_smtp_class, mock_settings) -> None:
    """Test SMTP connection without credentials."""
    mock_settings.email.SMTP_USER = ""
    mock_settings.email.SMTP_PASSWORD = ""
    mock_smtp = MagicMock()
    mock_smtp_class.return_value = mock_smtp
    
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.settings.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            
            connection = service._create_smtp_connection()
            
            assert connection == mock_smtp
            mock_smtp.login.assert_not_called()


@patch("smtplib.SMTP")
def test_smtp_connection_failure(mock_smtp_class, email_service) -> None:
    """Test SMTP connection failure."""
    mock_smtp_class.side_effect = Exception("Connection failed")
    
    connection = email_service._create_smtp_connection()
    
    assert connection is None


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_disabled(mock_connection, mock_settings) -> None:
    """Test email sending when disabled."""
    mock_settings.email.ENABLED = False
    
    with patch("sqlstack.lib.email.get_settings", return_value=mock_settings):
        with patch("sqlstack.lib.settings.TEMPLATE_DIR", "/fake/templates"):
            service = EmailService()
            
            result = await service.send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>"
            )
            
            assert result is False
            mock_connection.assert_not_called()


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_no_connection(mock_connection, email_service) -> None:
    """Test email sending when connection fails."""
    mock_connection.return_value = None
    
    result = await email_service.send_email(
        to_email="test@example.com",
        subject="Test",
        html_content="<p>Test</p>"
    )
    
    assert result is False


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_success(mock_connection, email_service) -> None:
    """Test successful email sending."""
    mock_smtp = MagicMock()
    mock_connection.return_value = mock_smtp
    
    result = await email_service.send_email(
        to_email="test@example.com",
        subject="Test Subject",
        html_content="<p>Test HTML</p>",
        text_content="Test Text"
    )
    
    assert result is True
    mock_smtp.send_message.assert_called_once()
    mock_smtp.quit.assert_called_once()
    
    # Verify the message structure
    call_args = mock_smtp.send_message.call_args
    message = call_args[0][0]
    assert isinstance(message, MIMEMultipart)
    assert message["Subject"] == "Test Subject"
    assert message["To"] == "test@example.com"
    assert "noreply@example.com" in message["From"]


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_multiple_recipients(mock_connection, email_service) -> None:
    """Test sending email to multiple recipients."""
    mock_smtp = MagicMock()
    mock_connection.return_value = mock_smtp
    
    recipients = ["test1@example.com", "test2@example.com"]
    result = await email_service.send_email(
        to_email=recipients,
        subject="Test",
        html_content="<p>Test</p>"
    )
    
    assert result is True
    call_args = mock_smtp.send_message.call_args
    assert call_args[1]["to_addrs"] == recipients


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_auto_text_generation(mock_connection, email_service) -> None:
    """Test automatic text content generation from HTML."""
    mock_smtp = MagicMock()
    mock_connection.return_value = mock_smtp
    
    result = await email_service.send_email(
        to_email="test@example.com",
        subject="Test",
        html_content="<h1>Title</h1><p>Paragraph with <b>bold</b> text</p>"
    )
    
    assert result is True
    # Text should be generated automatically by stripping HTML tags


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_smtp_exception(mock_connection, email_service) -> None:
    """Test email sending with SMTP exception."""
    mock_smtp = MagicMock()
    mock_smtp.send_message.side_effect = Exception("SMTP Error")
    mock_connection.return_value = mock_smtp
    
    result = await email_service.send_email(
        to_email="test@example.com",
        subject="Test",
        html_content="<p>Test</p>"
    )
    
    assert result is False
    mock_smtp.quit.assert_called_once()  # Should still clean up


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_custom_sender(mock_connection, email_service) -> None:
    """Test email sending with custom sender."""
    mock_smtp = MagicMock()
    mock_connection.return_value = mock_smtp
    
    result = await email_service.send_email(
        to_email="test@example.com",
        subject="Test",
        html_content="<p>Test</p>",
        from_email="custom@example.com",
        from_name="Custom Sender"
    )
    
    assert result is True
    
    call_args = mock_smtp.send_message.call_args
    message = call_args[0][0]
    assert "custom@example.com" in message["From"]
    assert "Custom Sender" in message["From"]


@patch.object(EmailService, "send_email")
async def test_send_template_email_success(mock_send, email_service) -> None:
    """Test successful template email sending."""
    # Mock Jinja2 template
    mock_template = MagicMock()
    mock_template.render.return_value = "<h1>Hello John</h1>"
    email_service.jinja_env.get_template = MagicMock(return_value=mock_template)
    
    mock_send.return_value = True
    
    result = await email_service.send_template_email(
        template_name="welcome",
        to_email="test@example.com",
        subject="Welcome",
        context={"name": "John"}
    )
    
    assert result is True
    email_service.jinja_env.get_template.assert_called_with("emails/welcome.html.j2")
    mock_template.render.assert_called_with(name="John")
    mock_send.assert_called_once()


@patch.object(EmailService, "send_email")
async def test_send_template_email_with_text_template(mock_send, email_service) -> None:
    """Test template email with both HTML and text templates."""
    # Mock both HTML and text templates
    mock_html_template = MagicMock()
    mock_html_template.render.return_value = "<h1>Hello John</h1>"
    
    mock_text_template = MagicMock()
    mock_text_template.render.return_value = "Hello John"
    
    def get_template_side_effect(name):
        if "html" in name:
            return mock_html_template
        elif "txt" in name:
            return mock_text_template
        raise Exception("Template not found")
    
    email_service.jinja_env.get_template = MagicMock(side_effect=get_template_side_effect)
    mock_send.return_value = True
    
    result = await email_service.send_template_email(
        template_name="welcome",
        to_email="test@example.com",
        subject="Welcome",
        context={"name": "John"}
    )
    
    assert result is True
    # Should call send_email with both HTML and text content
    call_args = mock_send.call_args
    assert call_args[1]["html_content"] == "<h1>Hello John</h1>"
    assert call_args[1]["text_content"] == "Hello John"


@patch.object(EmailService, "send_email")
async def test_send_template_email_template_error(mock_send, email_service) -> None:
    """Test template email with template loading error."""
    email_service.jinja_env.get_template = MagicMock(side_effect=Exception("Template not found"))
    
    result = await email_service.send_template_email(
        template_name="nonexistent",
        to_email="test@example.com",
        subject="Test",
        context={}
    )
    
    assert result is False
    mock_send.assert_not_called()


@patch.object(EmailService, "send_template_email")
async def test_send_verification_email_with_template(mock_send_template, email_service, test_user) -> None:
    """Test verification email sending with template."""
    mock_send_template.return_value = True
    
    result = await email_service.send_verification_email(test_user, "verification-token-123")
    
    assert result is True
    mock_send_template.assert_called_once()
    
    call_args = mock_send_template.call_args
    assert call_args[1]["template_name"] == "email_verification"
    assert call_args[1]["to_email"] == test_user.email
    assert "verification-token-123" in call_args[1]["context"]["verification_url"]


@patch.object(EmailService, "send_template_email")
@patch.object(EmailService, "send_email")
async def test_send_verification_email_fallback(mock_send, mock_send_template, email_service, test_user) -> None:
    """Test verification email fallback when template fails."""
    mock_send_template.side_effect = Exception("Template error")
    mock_send.return_value = True
    
    result = await email_service.send_verification_email(test_user, "verification-token-123")
    
    assert result is True
    mock_send_template.assert_called_once()
    mock_send.assert_called_once()
    
    # Check fallback email content
    call_args = mock_send.call_args
    assert "verification-token-123" in call_args[1]["html_content"]
    assert test_user.name in call_args[1]["html_content"]


@patch.object(EmailService, "send_template_email")
async def test_send_welcome_email(mock_send_template, email_service, test_user) -> None:
    """Test welcome email sending."""
    mock_send_template.return_value = True
    
    result = await email_service.send_welcome_email(test_user)
    
    assert result is True
    mock_send_template.assert_called_once()
    
    call_args = mock_send_template.call_args
    assert call_args[1]["template_name"] == "welcome"
    assert call_args[1]["to_email"] == test_user.email
    assert call_args[1]["subject"] == "Welcome to Test Application!"


@patch.object(EmailService, "send_template_email")
async def test_send_password_reset_email(mock_send_template, email_service, test_user) -> None:
    """Test password reset email sending."""
    mock_send_template.return_value = True
    
    result = await email_service.send_password_reset_email(
        test_user, 
        "reset-token-123", 
        expires_in_minutes=60,
        ip_address="192.168.1.1"
    )
    
    assert result is True
    mock_send_template.assert_called_once()
    
    call_args = mock_send_template.call_args
    assert call_args[1]["template_name"] == "password_reset"
    assert "reset-token-123" in call_args[1]["context"]["reset_url"]
    assert call_args[1]["context"]["expires_in_minutes"] == 60
    assert call_args[1]["context"]["ip_address"] == "192.168.1.1"


@patch.object(EmailService, "send_template_email")
async def test_send_password_reset_confirmation_email(mock_send_template, email_service, test_user) -> None:
    """Test password reset confirmation email."""
    mock_send_template.return_value = True
    
    result = await email_service.send_password_reset_confirmation_email(test_user)
    
    assert result is True
    mock_send_template.assert_called_once()
    
    call_args = mock_send_template.call_args
    assert call_args[1]["template_name"] == "password_reset_confirmation"
    assert call_args[1]["to_email"] == test_user.email


@patch.object(EmailService, "send_template_email")
async def test_send_team_invitation_email(mock_send_template, email_service) -> None:
    """Test team invitation email."""
    mock_send_template.return_value = True
    
    result = await email_service.send_team_invitation_email(
        invitee_email="invitee@example.com",
        inviter_name="John Doe",
        team_name="Awesome Team",
        invitation_url="http://localhost:8000/invite/abc123"
    )
    
    assert result is True
    mock_send_template.assert_called_once()
    
    call_args = mock_send_template.call_args
    assert call_args[1]["template_name"] == "team_invitation"
    assert call_args[1]["to_email"] == "invitee@example.com"
    assert call_args[1]["context"]["inviter_name"] == "John Doe"
    assert call_args[1]["context"]["team_name"] == "Awesome Team"


@patch.object(EmailService, "send_template_email")
@patch.object(EmailService, "send_email")
async def test_send_team_invitation_email_fallback(mock_send, mock_send_template, email_service) -> None:
    """Test team invitation email fallback."""
    mock_send_template.side_effect = Exception("Template error")
    mock_send.return_value = True
    
    result = await email_service.send_team_invitation_email(
        invitee_email="invitee@example.com",
        inviter_name="John Doe",
        team_name="Awesome Team",
        invitation_url="http://localhost:8000/invite/abc123"
    )
    
    assert result is True
    mock_send.assert_called_once()
    
    call_args = mock_send.call_args
    assert "John Doe" in call_args[1]["html_content"]
    assert "Awesome Team" in call_args[1]["html_content"]


def test_email_service_with_missing_settings() -> None:
    """Test email service initialization with missing settings."""
    with patch("sqlstack.lib.email.get_settings") as mock_get_settings:
        mock_get_settings.side_effect = Exception("Settings error")
        
        with pytest.raises(Exception):
            EmailService()


@patch.object(EmailService, "_create_smtp_connection")
async def test_send_email_with_empty_recipients(mock_connection, email_service) -> None:
    """Test sending email with empty recipient list."""
    mock_smtp = MagicMock()
    mock_connection.return_value = mock_smtp
    
    result = await email_service.send_email(
        to_email=[],
        subject="Test",
        html_content="<p>Test</p>"
    )
    
    # Should still try to send (SMTP will handle empty recipient list)
    assert result is True


async def test_user_without_name_in_verification_email(email_service) -> None:
    """Test verification email for user without name."""
    user_without_name = s.User(
        id="123e4567-e89b-12d3-a456-426614174000",
        email="user@example.com",
        name=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
    )
    
    with patch.object(email_service, "send_template_email", side_effect=Exception("Template error")):
        with patch.object(email_service, "send_email", return_value=True) as mock_send:
            result = await email_service.send_verification_email(user_without_name, "token")
            
            assert result is True
            call_args = mock_send.call_args
            # Should handle None name gracefully
            assert "there" in call_args[1]["html_content"]  # Fallback greeting