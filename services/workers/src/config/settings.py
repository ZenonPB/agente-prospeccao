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

settings = Settings()