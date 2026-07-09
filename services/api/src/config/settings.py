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

settings = Settings()
