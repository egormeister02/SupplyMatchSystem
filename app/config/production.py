from .base import BaseConfig
from dotenv import load_dotenv

# Загружаем продакшн переменные окружения
load_dotenv(".env.prod")

class ProductionConfig(ProductionConfig):
    # Настройки для продакшена
    WEBHOOK_URL: str
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_SECRET: str = ""  # Дополнительная защита для вебхука
    
    # Другие специфичные для продакшена настройки
    DEBUG: bool = False
