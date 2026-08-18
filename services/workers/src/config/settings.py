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

    # Chave mestre para criptografia dos secrets BYOK.
    # Deve ser um token Fernet (base64 de 32 bytes). Se vazio, deriva-se uma
    # chave determinística do DATABASE_URL (adequado só para desenvolvimento).
    SECRETS_ENCRYPTION_KEY: str = Field("", description='Chave Fernet para organization_secrets')

    # Teto diário de chamadas por provedor (default do pool global).
    # A org pode sobrescrever por provedor via `organizations.api_quota`.
    PROVIDER_DAILY_QUOTA: dict = Field(
        default_factory=lambda: {
            "GOOGLE_API_KEY": 100,
            "GROQ_API_KEY": 2000,
        },
        description='Teto diário de chamadas por provedor (key_name → limite)',
    )

    # Resiliência a rate-limit da Groq (HTTP 429 / janela de ~60s do tier free).
    # Pacing: intervalo mínimo entre o INÍCIO de chamadas Groq no processo
    # (evita estourar a janela de TPM/RPM em batches). Retry: em 429 a Groq
    # informa `Retry-After`; sem ele, usa backoff exponencial base*2^tentativa
    # limitado a GROQ_RETRY_MAX_SECONDS.
    GROQ_MIN_INTERVAL_SECONDS: float = Field(
        20.0,
        description='Intervalo mínimo entre chamadas Groq (pacing, em segundos)',
    )
    GROQ_MAX_RETRIES: int = Field(
        5,
        description='Máximo de tentativas por chamada Groq em 429/5xx (1 = sem retry)',
    )
    GROQ_RETRY_BASE_SECONDS: float = Field(
        4.0,
        description='Backoff base (s) para retry sem header Retry-After',
    )
    GROQ_RETRY_MAX_SECONDS: float = Field(
        60.0,
        description='Teto do backoff (s) para retry sem header Retry-After',
    )

    # Modelos Groq — config centralizada para trocar de modelo sem editar os
    # serviços individualmente. CLASSIFY = tarefas de classificação (scoring e
    # router de template, respostas curtas); GENERATION = texto client-facing
    # (outreach, segmentos, brief, templates gerados).
    GROQ_MODEL_CLASSIFY: str = Field(
        "openai/gpt-oss-20b",
        description='Modelo Groq de classificação (scoring/router)',
    )
    GROQ_MODEL_GENERATION: str = Field(
        "qwen/qwen3.6-27b",
        description='Modelo Groq de geração (outreach/segmentos/brief/templates)',
    )

settings = Settings()