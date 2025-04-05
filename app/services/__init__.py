"""
Service modules for working with external resources.
"""

from app.services.database import (
    Base, AsyncSessionLocal, init_db, get_db_session, DBService
)

# Инициализируем S3 только если модуль storage импортирован
try:
    from app.services.storage import s3_service
except ImportError:
    s3_service = None

# Инициализируем локальное хранилище
from app.services.local_storage import local_storage_service

__all__ = [
    'Base', 
    'AsyncSessionLocal', 
    'init_db', 
    'get_db_session', 
    'DBService',
    's3_service',
    'local_storage_service'
]
