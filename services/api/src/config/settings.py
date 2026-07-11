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

    # Password reset
    RESET_TOKEN_EXPIRY_HOURS: int = Field(2, description='Horas até expiração do token de reset de senha')
    APP_BASE_URL: str = Field("http://localhost:3000", description='URL base da aplicação para links de reset')

    # SMTP
    SMTP_HOST: str = Field("", description='Servidor SMTP')
    SMTP_PORT: int = Field(587, description='Porta SMTP')
    SMTP_USER: str = Field("", description='Usuário SMTP')
    SMTP_PASSWORD: str = Field("", description='Senha SMTP')
    SMTP_FROM_EMAIL: str = Field("noreply@agente-prospeccao.com", description='E-mail remetente')
    SMTP_FROM_NAME: str = Field("Agente Prospecção", description='Nome do remetente')

settings = Settings()
