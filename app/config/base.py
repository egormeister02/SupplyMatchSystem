import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

class BaseConfig(BaseSettings):
    # Общие настройки для всех сред
    BOT_TOKEN: str
    DATABASE_URL: str
    S3_BUCKET_NAME: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_ENDPOINT_URL: str
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = 'Europe/Moscow'
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ADMIN_IDS: list = []
    
    class Config:
        env_file_encoding = "utf-8"
