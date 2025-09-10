import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

class BaseConfig(BaseSettings):
    # Общие настройки для всех сред
    BOT_TOKEN: str
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = 'Europe/Moscow'
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    KILL_SECRET_TOKEN: str = "sus"
    
    # DeepSeek settings
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    
    QUEUE_WORKERS: int = 5  # Количество параллельных воркеров очереди, можно переопределить через .env
    
    class Config:
        env_file_encoding = "utf-8"
