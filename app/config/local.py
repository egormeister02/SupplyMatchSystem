from .base import BaseConfig
from dotenv import load_dotenv

# Загружаем локальные переменные окружения
load_dotenv(".env.local")

class LocalConfig(BaseConfig):
    # Настройки для локальной разработки
    WEBHOOK_URL: str = "https://your-ngrok-url.ngrok-free.app"  # Будет заменено скриптом
    WEBHOOK_PATH: str = "/webhook"
    
    # Использование ngrok для локальной разработки
    USE_NGROK: bool = True
    NGROK_AUTH_TOKEN: str = ""
    
    # Другие специфичные для локальной разработки настройки
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Добавить недостающий атрибут
    RECREATE_DB_SCHEMA: bool = False
