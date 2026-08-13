from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # Ambiente: 'development' (padrão) ou 'production'. Em produção, SMTP ausente
    # não é aceito silenciosamente — envio falha em vez de "fingir" que funcionou.
    ENVIRONMENT: str = Field("development", description="development | production")

    # Cadence scheduler (item 3.7.2) — intervalo do poll de follow-ups vencidos.
    CADENCE_POLL_SECONDS: int = Field(60, description='Segundos entre verificações de follow-ups vencidos')

    # Re-enfileiramento de leads PERDIDO (business-rules): carência em dias para
    # o lead voltar à fila (PERDIDO → NOVO) e intervalo do poll do job no main.py.
    LOST_REQUEUE_DAYS: int = Field(90, description='Dias em PERDIDO até o lead voltar à fila (0 desativa)')
    LOST_REQUEUE_POLL_SECONDS: int = Field(3600, description='Segundos entre verificações de leads PERDIDO vencidos')

    # Item 4.3 — throttling: teto diário de envios automáticos por org quando a
    # org não define o próprio `daily_email_limit`. A janela de espalhamento
    # também é configurável por org (`send_window_start/end`, HH:MM no fuso do
    # servidor); este é apenas o fallback de teto diário.
    DAILY_EMAIL_LIMIT: int = Field(40, description='Teto diário default de envios automáticos por org')

    # Origins permitidas no CORS (vírgula-separado). Deploy: incluir o domínio do frontend.
    CORS_ORIGINS: str = Field("http://localhost:3000,http://localhost:3001", description='Origins CORS separadas por vírgula')

    # Password reset
    RESET_TOKEN_EXPIRY_HOURS: int = Field(2, description='Horas até expiração do token de reset de senha')
    APP_BASE_URL: str = Field("http://localhost:3001", description='URL base da aplicação para links de reset')

    # SMTP
    SMTP_HOST: str = Field("", description='Servidor SMTP')
    SMTP_PORT: int = Field(587, description='Porta SMTP')
    SMTP_USER: str = Field("", description='Usuário SMTP')
    SMTP_PASSWORD: str = Field("", description='Senha SMTP')
    SMTP_FROM_EMAIL: str = Field("noreply@agente-prospeccao.com", description='E-mail remetente')
    SMTP_FROM_NAME: str = Field("Agente Prospecção", description='Nome do remetente')

    # Inbound email (item 3.3) — segredo compartilhado com o provedor de
    # inbound (Postmark/SendGrid). Vazio = webhook desativado (404).
    EMAIL_WEBHOOK_SECRET: str = Field("", description='Segredo do webhook de inbound (resposta/STOP)')

    # Tracking de abertura/clique (4.2) — base pública da API que o cliente de
    # e-mail do destinatário acessa (ex.: https://api.alphamec.com.br). Vazio =
    # tracking desativado (não injeta pixel/redirect nos envios).
    TRACKING_BASE_URL: str = Field("", description='URL pública da API para pixel/redirect de tracking')

settings = Settings()
