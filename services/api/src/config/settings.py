from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Union

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='../../.env',
        extra='ignore'
    )

    DATABASE_URL: str = Field(..., description='URL de conexão com o banco de dados PostgreSQL')
    JWT_SECRET: str = Field(..., description='Chave secreta para assinatura de tokens JWT')
    JWT_ALGORITHM: str = Field("HS256", description='Algoritmo de assinatura JWT')
    JWT_EXPIRES_HOURS: int = Field(24, description='Horas até expiração do token JWT')
    JWT_ISSUER: str = Field("prospect-ai", description='Emissor (iss) esperado nos tokens JWT')
    JWT_AUDIENCE: str = Field("prospect-ai-api", description='Audiência (aud) esperada nos tokens JWT')
    ENVIRONMENT: str = Field("development", description="development | production")

    CADENCE_POLL_SECONDS: int = Field(60, description='Segundos entre verificações de follow-ups vencidos')
    LOST_REQUEUE_DAYS: int = Field(90, description='Dias em PERDIDO até o lead voltar à fila (0 desativa)')
    LOST_REQUEUE_POLL_SECONDS: int = Field(3600, description='Segundos entre verificações de leads PERDIDO vencidos')
    CADENCE_CLOSE_GRACE_DAYS: int = Field(7, description='Dias após o encerramento sem resposta até marcar PERDIDO')
    CADENCE_CLOSE_POLL_SECONDS: int = Field(3600, description='Segundos entre verificações de cadências encerradas')
    DELIVERABILITY_POLL_SECONDS: int = Field(3600, description='Segundos entre verificações de saúde de entregabilidade')
    JOB_POLL_SECONDS: int = Field(5, description='Segundos entre verificações de Jobs PENDING')
    EVENT_EXPIRATION_POLL_SECONDS: int = Field(3600, description='Segundos entre atualizações de expiração de eventos')

    # O loop existe sempre, mas só faz I/O para organizações que configuraram
    # explicitamente as cotas correspondentes em api_quota.
    CONTINUOUS_INTELLIGENCE_POLL_SECONDS: int = Field(
        3600, ge=300, description='Intervalo do scheduler de inteligência contínua'
    )
    CONTINUOUS_INTELLIGENCE_MIN_INTERVAL_HOURS: int = Field(
        12, ge=1, le=168, description='Intervalo mínimo entre ciclos por organização'
    )
    CONTINUOUS_INTELLIGENCE_BATCH_SIZE: int = Field(
        25, ge=1, le=200, description='Máximo de leads revisados por ciclo e organização'
    )
    INTENT_PROVIDER_MAX_RETRIES: int = Field(1, ge=0, le=5, description='Retries dos feeds de intent')
    JOB_INTENT_URL: str = Field("", description='Endpoint HTTPS de vagas/job signals')
    JOB_INTENT_TOKEN: str = Field("", description='Bearer opcional do feed de vagas')
    NEWS_INTENT_URL: str = Field("", description='Endpoint HTTPS de notícias corporativas')
    NEWS_INTENT_TOKEN: str = Field("", description='Bearer opcional do feed de notícias')
    SOCIAL_INTENT_URL: str = Field("", description='Endpoint HTTPS de sinais sociais')
    SOCIAL_INTENT_TOKEN: str = Field("", description='Bearer opcional do feed social')
    EMAIL_CATCHALL_PROBE_ENABLED: bool = Field(
        False, description='Habilita globalmente probe SMTP; ainda exige cota explícita da organização'
    )

    DAILY_EMAIL_LIMIT: int = Field(40, description='Teto diário default de envios automáticos por org')
    CORS_ORIGINS: Union[list[str], str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://prospect-api-h1i0.onrender.com"
    ]

    RESET_TOKEN_EXPIRY_HOURS: int = Field(2, description='Horas até expiração do token de reset de senha')
    APP_BASE_URL: str = Field("http://localhost:3001", description='URL base da aplicação para links de reset')

    SMTP_HOST: str = Field("", description='Servidor SMTP')
    SMTP_PORT: int = Field(587, description='Porta SMTP')
    SMTP_USER: str = Field("", description='Usuário SMTP')
    SMTP_PASSWORD: str = Field("", description='Senha SMTP')
    SMTP_FROM_EMAIL: str = Field("noreply@prospect.ai", description='E-mail remetente')
    SMTP_FROM_NAME: str = Field("Prospect.ai", description='Nome do remetente')
    EMAIL_WEBHOOK_SECRET: str = Field("", description='Segredo do webhook de inbound')
    TRACKING_BASE_URL: str = Field("", description='URL pública da API para tracking')

    EVENT_DISCOVERY_URL: str = Field("", description='Endpoint JSON externo de eventos (opt-in)')
    EVENT_DISCOVERY_TOKEN: str = Field("", description='Token opcional Bearer do provider de eventos')
    EVENT_DISCOVERY_MAX_RETRIES: int = Field(1, ge=0, le=5, description='Retentativas do provider de eventos')

settings = Settings()
