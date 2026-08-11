import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='../../.env',
        extra='ignore'
    )

    POSTGRES_USER: str = Field(..., description='Usuário do banco de dados PostgreSQL')
    POSTGRES_PASSWORD: str = Field(..., description='Senha do banco de dados PostgreSQL')
    POSTGRES_DB: str = Field(..., description='Nome do banco de dados PostgreSQL')

    DATABASE_URL: str = Field(..., description='URL de conexão com o banco de dados PostgreSQL')

    PGADMIN_EMAIL: str = Field(..., description='Email de login do pgAdmin')
    PGADMIN_PASSWORD: str = Field(..., description='Senha de login do pgAdmin')

    GROQ_API_KEY: str = Field(..., description='Chave de API da Groq')
    GOOGLE_API_KEY: str = Field(..., description='Chave de API do Google')
    # Opcional — Hunter.io para e-mail de decisor (BYOK futura).
    # Sem a chave, o enriquecimento de e-mail usa fallback gratuito (CNPJ + heurística).
    HUNTER_API_KEY: str = Field("", description='Chave opcional da API Hunter.io')

    # Chave mestre para criptografia dos secrets BYOK (item 3.5).
    # Deve ser um token Fernet (base64 de 32 bytes). Se vazio, deriva-se uma
    # chave determinística do DATABASE_URL (adequado só para desenvolvimento).
    SECRETS_ENCRYPTION_KEY: str = Field("", description='Chave Fernet para organization_secrets')

    # Item 4.14 — teto diário de chamadas por provedor (default do pool global).
    # A org pode sobrescrever por provedor via `organizations.api_quota`.
    PROVIDER_DAILY_QUOTA: dict = Field(
        default_factory=lambda: {
            "GOOGLE_API_KEY": 100,
            "GROQ_API_KEY": 2000,
        },
        description='Teto diário de chamadas por provedor (key_name → limite)',
    )

settings = Settings()