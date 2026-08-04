"""Email service for password reset and transactional emails.

Uses SMTP via stdlib. Falls back to logging in development when SMTP
is not configured.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config.settings import settings

logger = logging.getLogger(__name__)


def _is_smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Envia e-mail transacional genérico via SMTP (ou loga no console em dev).

    Item 3.7: usado pela cadência de follow-up (humano-no-loop envia pela UI;
    envio automático apenas quando a org ativa `auto_send_email`). Em dev, sem
    SMTP configurado, o conteúdo é impresso no log — permitindo E2E sem rede.
    """
    if _is_smtp_configured():
        return _send_smtp(to_email, subject, body)

    logger.info("=== EMAIL (SMTP not configured — human-in-the-loop) ===")
    logger.info("To: %s", to_email)
    logger.info("Subject: %s", subject)
    logger.info("Body: \n%s", body)
    logger.info("=== END EMAIL ===")
    return True


def send_password_reset_email(to_email: str, reset_link: str, user_name: str) -> bool:
    """Send password reset email via SMTP, or log to console in dev."""
    subject = "Redefinição de senha - Agente Prospecção"
    body = f"""Olá {user_name},

Recebemos uma solicitação de redefinição de senha para sua conta.

Clique no link abaixo para criar uma nova senha:

{reset_link}

Este link expira em {settings.RESET_TOKEN_EXPIRY_HOURS} horas.

Se você não solicitou esta alteração, ignore este e-mail.

Atenciosamente,
Equipe Agente Prospecção
"""

    if _is_smtp_configured():
        return _send_smtp(to_email, subject, body)

    logger.info("=== PASSWORD RESET (SMTP not configured) ===")
    logger.info("To: %s", to_email)
    logger.info("Subject: %s", subject)
    logger.info("Link: %s", reset_link)
    logger.info("Body: \n%s", body)
    logger.info("=== END PASSWORD RESET ===")
    return True


def _send_smtp(to_email: str, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())

        logger.info("Password reset email sent to %s", to_email)
        return True
    except smtplib.SMTPException as e:
        logger.error("Failed to send password reset email to %s: %s", to_email, e)
        return False
