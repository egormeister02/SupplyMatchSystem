"""
Service modules for working with external resources.
"""

from app.services.database import (
    Base, AsyncSessionLocal, init_db, get_db_session, DBService
)

# Инициализируем локальное хранилище
from app.services.local_storage import local_storage_service

# Импортируем сервис для работы с чатом администраторов
from app.services.admin_chat import admin_chat_service

__all__ = [
    'Base', 
    'AsyncSessionLocal', 
    'init_db', 
    'get_db_session', 
    'DBService',
    's3_service',
    'local_storage_service',
    'admin_chat_service'
]
