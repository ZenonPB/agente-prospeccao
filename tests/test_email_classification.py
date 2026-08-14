"""Testes da classificação de falhas SMTP — bounce permanente vs transitório."""
import smtplib

from src.services.email_service import _classify_error


def test_recipients_refused_5xx_e_permanente():
    exc = smtplib.SMTPRecipientsRefused({"a@b.com": (550, b"User unknown")})
    permanent, _ = _classify_error(exc)
    assert permanent is True


def test_recipients_refused_4xx_e_transitorio():
    exc = smtplib.SMTPRecipientsRefused({"a@b.com": (450, b"try again")})
    permanent, _ = _classify_error(exc)
    assert permanent is False


def test_response_5xx_permanente():
    exc = smtplib.SMTPResponseException(550, b"Message rejected")
    permanent, _ = _classify_error(exc)
    assert permanent is True


def test_response_4xx_transitorio():
    exc = smtplib.SMTPResponseException(451, b"temporary failure")
    permanent, _ = _classify_error(exc)
    assert permanent is False


def test_connection_error_transitorio():
    exc = smtplib.SMTPServerDisconnected("conexão caiu")
    permanent, _ = _classify_error(exc)
    assert permanent is False


def test_sender_refused_permanente():
    exc = smtplib.SMTPSenderRefused(553, b"sender refused", "x@y.com")
    permanent, _ = _classify_error(exc)
    assert permanent is True
