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

    POSTGRES_USER: str = Field("", description='Usuário do banco de dados PostgreSQL')
    POSTGRES_PASSWORD: str = Field("", description='Senha do banco de dados PostgreSQL')
    POSTGRES_DB: str = Field("", description='Nome do banco de dados PostgreSQL')
    DATABASE_URL: str = Field(..., description='URL de conexão com o banco de dados PostgreSQL')
    ENVIRONMENT: str = Field("development", description="development | test | production")
    PGADMIN_EMAIL: str = Field("", description='Email de login do pgAdmin')
    PGADMIN_PASSWORD: str = Field("", description='Senha de login do pgAdmin')

    GROQ_API_KEY: str = Field(..., description='Chave de API da Groq')
    GOOGLE_API_KEY: str = Field(..., description='Chave de API do Google')
    HUNTER_API_KEY: str = Field("", description='Chave opcional da API Hunter.io')

    PEOPLE_DISCOVERY_URL: str = Field("", description='Endpoint JSON externo de pessoas (opt-in)')
    PEOPLE_DISCOVERY_TOKEN: str = Field("", description='Token opcional Bearer do provider de pessoas')
    PEOPLE_DISCOVERY_MAX_RETRIES: int = Field(1, ge=0, le=5, description='Retentativas do provider de pessoas')

    SECRETS_ENCRYPTION_KEY: str = Field("", description='Chave Fernet para organization_secrets')

    PROVIDER_DAILY_QUOTA: dict = Field(
        default_factory=lambda: {
            "GOOGLE_API_KEY": 100,
            "GROQ_API_KEY": 2000,
            "HUNTER_API_KEY": 50,
            "WEBSITE_PEOPLE_PROVIDER": 0,
            "PEOPLE_DISCOVERY_HTTP": 0,
            # Inteligência contínua e feeds externos são sempre opt-in por org.
            "CONTINUOUS_INTELLIGENCE": 0,
            "JOB_INTENT_HTTP": 0,
            "NEWS_INTENT_HTTP": 0,
            "SOCIAL_INTENT_HTTP": 0,
            # Probe SMTP é ativo; não recebe cota global implícita.
            "EMAIL_CATCHALL_PROBE": 0,
        },
        description='Teto diário de chamadas por provedor (key_name → limite)',
    )

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
    GROQ_MODEL_CLASSIFY: str = Field(
        "openai/gpt-oss-20b",
        description='Modelo Groq de classificação (scoring/router)',
    )
    GROQ_MODEL_GENERATION: str = Field(
        "qwen/qwen3.6-27b",
        description='Modelo Groq de geração (outreach/segmentos/brief/templates)',
    )

settings = Settings()
