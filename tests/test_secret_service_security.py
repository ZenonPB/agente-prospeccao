"""Contratos de segurança para secrets criptografados em repouso."""


def test_producao_exige_chave_mestre_para_criptografar(monkeypatch):
    """Nunca usar a derivação determinística do banco em produção."""
    from services import secret_service

    monkeypatch.setattr(secret_service.settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(secret_service.settings, "SECRETS_ENCRYPTION_KEY", "")

    try:
        secret_service.encrypt_value("valor-confidencial")
    except RuntimeError as exc:
        assert "SECRETS_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("produção deve exigir SECRETS_ENCRYPTION_KEY")


def test_producao_exige_chave_mestre_para_descriptografar(monkeypatch):
    """A exigência também vale para leitura de secrets já armazenados."""
    from services import secret_service

    monkeypatch.setattr(secret_service.settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(secret_service.settings, "SECRETS_ENCRYPTION_KEY", "")

    try:
        secret_service.decrypt_value("token")
    except RuntimeError as exc:
        assert "SECRETS_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("produção deve exigir SECRETS_ENCRYPTION_KEY")


def test_desenvolvimento_mantem_fallback_compatibilidade(monkeypatch):
    """O fallback determinístico permanece disponível apenas fora de produção."""
    from services import secret_service

    monkeypatch.setattr(secret_service.settings, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(secret_service.settings, "SECRETS_ENCRYPTION_KEY", "")

    token = secret_service.encrypt_value("valor-local")

    assert secret_service.decrypt_value(token) == "valor-local"


def test_chave_mestre_configurada_funciona_em_producao(monkeypatch):
    """Produção funciona normalmente com uma chave Fernet explícita."""
    from cryptography.fernet import Fernet
    from services import secret_service

    monkeypatch.setattr(secret_service.settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(
        secret_service.settings,
        "SECRETS_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )

    token = secret_service.encrypt_value("valor-prod")

    assert secret_service.decrypt_value(token) == "valor-prod"