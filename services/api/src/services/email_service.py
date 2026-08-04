"""Email service for transactional and cadence emails.

Uses SMTP via stdlib. Falls back to logging in development when SMTP
is not configured (dry-run), and fails loudly in production.

Changes from the audit (fix/go-live-prep):
- `EmailSendResult` distingue envio/bounce permanente/erro transitório.
- Headers de threading (`Message-ID`, `In-Reply-To`, `References`) para
  respostas formarem thread.
- Nunca loga o corpo (PII) — só destinatário e assunto.
- Em `production` sem SMTP configurado, envio falha (não "finge" que enviou).
"""
import logging
import smtplib
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from typing import List, Optional

from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailSendResult:
    """Resultado de um envio de e-mail.

    - `sent`: entrega aceita pelo servidor.
    - `permanent`: falha permanente (bounce 5xx / remetente recusado) — não
      faz sentido re-tentar o mesmo endereço.
    - `message_id`: Message-ID gerado no envio (usado para thread de follow-ups).
    - `error`: mensagem de erro legível (sem PII).
    """
    sent: bool = False
    permanent: bool = False
    message_id: Optional[str] = None
    error: Optional[str] = None

    def __bool__(self) -> bool:
        return self.sent


def _is_smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _message_id_from(result: Optional[str], hostname: str = "agente-prospeccao.com") -> str:
    """Gera um Message-ID estável para thread (ou reutiliza um já existente)."""
    if result:
        return result
    return make_msgid(domain=hostname)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
    message_id: Optional[str] = None,
) -> EmailSendResult:
    """Envia e-mail transacional via SMTP.

    `from_email`/`from_name`: remetente (default: settings). Permite remetente
    por org (item 4.1 da auditoria).
    `in_reply_to`/`references`: headers de threading — follow-ups apontam para
    o Message-ID da etapa anterior da cadência.
    """
    from_email = from_email or settings.SMTP_FROM_EMAIL
    from_name = from_name or settings.SMTP_FROM_NAME

    if not _is_smtp_configured():
        if settings.ENVIRONMENT == "production":
            logger.error("SMTP não configurado em produção — envio para %s bloqueado", to_email)
            return EmailSendResult(sent=False, permanent=True, error="SMTP não configurado em produção")
        # Dev: dry-run. Loga só destinatário e assunto (nunca o corpo — PII).
        mid = _message_id_from(message_id)
        logger.info("[DRY-RUN EMAIL] to=%s subject=%r message_id=%s", to_email, subject, mid)
        return EmailSendResult(sent=True, message_id=mid, error="dry-run")

    return _send_smtp(
        to_email, subject, body,
        from_email=from_email, from_name=from_name,
        in_reply_to=in_reply_to, references=references, message_id=message_id,
    )


def send_password_reset_email(to_email: str, reset_link: str, user_name: str) -> bool:
    """Send password reset email via SMTP, or dry-run log in dev."""
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
        result = _send_smtp(to_email, subject, body)
        return result.sent

    logger.info("[DRY-RUN PASSWORD RESET] to=%s (link enviado em produção pelo SMTP)", to_email)
    return True


def _classify_error(exc: Exception) -> "tuple[bool, str]":
    """Classifica a falha em (permanente?, mensagem).

    Permanente (bounce 5xx / remetente recusado): não re-tentar.
    Transitória (4xx, timeout, desconexão): re-tentar.
    """
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [int(code) for code, _ in (exc.recipients or {}).values()]
        if codes and any(c >= 500 for c in codes):
            return True, f"bounce permanente ({','.join(map(str, codes))})"
        return False, f"destinatário recusado ({codes})"
    if isinstance(exc, smtplib.SMTPResponseException):
        code = exc.smtp_code or 0
        return (code >= 500, f"SMTP {code}: {exc.smtp_error}")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return True, "remetente recusado pelo servidor SMTP"
    if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, OSError)):
        return False, f"falha de conexão ({type(exc).__name__})"
    return False, f"erro de envio ({type(exc).__name__})"


def _send_smtp(
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
    message_id: Optional[str] = None,
) -> EmailSendResult:
    """Send email via SMTP, with threading headers and bounce classification."""
    mid = _message_id_from(message_id)

    msg = MIMEMultipart("alternative")
    msg["Message-ID"] = mid
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        refs = references or [in_reply_to]
        if in_reply_to not in refs:
            refs.append(in_reply_to)
        msg["References"] = " ".join(refs)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info("E-mail enviado para %s (message_id=%s)", to_email, mid)
        return EmailSendResult(sent=True, message_id=mid)
    except Exception as exc:  # noqa: BLE001 — classificação central de erros SMTP
        permanent, error = _classify_error(exc)
        logger.warning("Falha ao enviar para %s: %s (permanente=%s)", to_email, error, permanent)
        return EmailSendResult(sent=False, permanent=permanent, error=error)
