from typing import Optional, Any
from app.config.logging import app_logger
import os
import json

# Переменные конфигурации
ADMIN_GROUP_CHAT_ID = os.environ.get('ADMIN_GROUP_CHAT_ID')
if ADMIN_GROUP_CHAT_ID and ADMIN_GROUP_CHAT_ID.strip():
    try:
        ADMIN_GROUP_CHAT_ID = int(ADMIN_GROUP_CHAT_ID)
    except ValueError:
        app_logger.error(f"Некорректный ADMIN_GROUP_CHAT_ID: {ADMIN_GROUP_CHAT_ID}")
        ADMIN_GROUP_CHAT_ID = None
else:
    ADMIN_GROUP_CHAT_ID = None

# ID администраторов (через запятую)
ADMIN_IDS = os.environ.get('ADMIN_IDS', '')

# Методы для управления конфигурацией во время выполнения
def get_admin_chat_id() -> Optional[int]:
    """
    Получает текущий ID чата администраторов из конфигурации
    
    :return: ID чата администраторов или None если не настроен
    """
    return ADMIN_GROUP_CHAT_ID

def update_admin_chat_id(new_chat_id: int) -> bool:
    """
    Обновляет ID чата администраторов в конфигурации
    
    :param new_chat_id: Новый ID чата администраторов
    :return: True если обновление прошло успешно
    """
    global ADMIN_GROUP_CHAT_ID
    
    if new_chat_id and isinstance(new_chat_id, int):
        ADMIN_GROUP_CHAT_ID = new_chat_id
        app_logger.info(f"ID чата администраторов обновлен на {new_chat_id}")
        return True
    else:
        app_logger.error(f"Некорректный ID чата: {new_chat_id}")
        return False

def get_admin_ids():
    """Возвращает список числовых id админов из переменной окружения ADMIN_IDS"""
    raw = os.environ.get('ADMIN_IDS', '')
    ids = []
    try:
        # Пробуем как json-массив
        ids = json.loads(raw)
        if isinstance(ids, list):
            return [int(i) for i in ids]
    except Exception:
        pass
    # Если не json, пробуем как строку через запятую
    for part in raw.replace('[','').replace(']','').replace('"','').split(','):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except Exception:
                continue
    return ids

# Логируем информацию о настройках чата при запуске
if ADMIN_GROUP_CHAT_ID:
    app_logger.info(f"Настроен ID чата администраторов: {ADMIN_GROUP_CHAT_ID}")
else:
    app_logger.warning("ID чата администраторов не настроен. Используйте команду /chatid в нужном чате для получения ID") 