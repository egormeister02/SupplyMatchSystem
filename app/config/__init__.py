import os

# Определение текущего окружения
ENV = os.getenv("APP_ENV", "local")

if ENV == "production":
    from .production import ProductionConfig as Config
else:
    from .local import LocalConfig as Config

# Экспортируем конфигурацию
config = Config()
