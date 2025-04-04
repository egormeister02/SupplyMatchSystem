__version__ = "1.0.0"

# Импортируем ключевые компоненты для упрощения импорта в других модулях
from app.config import config
from app.services.database import init_db, AsyncSessionLocal, Base

__all__ = ["config", "init_db", "AsyncSessionLocal", "Base"]