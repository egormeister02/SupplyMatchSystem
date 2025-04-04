"""
Сервисные модули для работы с внешними ресурсами.
"""

from app.services.database import (
    Base, AsyncSessionLocal, init_db, get_db, DBService
)

# Инициализируем S3 только если модуль storage импортирован
try:
    from app.services.storage import s3_service
except ImportError:
    s3_service = None

__all__ = [
    'Base', 
    'AsyncSessionLocal', 
    'init_db', 
    'get_db', 
    'DBService',
    's3_service'
]
