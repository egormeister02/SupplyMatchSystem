"""
Handlers initialization
"""

import logging

from .base import router as base_router  # optional, keep minimal

logger = logging.getLogger(__name__)

def register_all_handlers(dp):
    """Регистрирует минимальный набор обработчиков."""
    try:
        dp.include_router(base_router)
        logger.info("Base handlers registered")
    except Exception as e:
        logger.error(f"Ошибка при регистрации базовых обработчиков: {e}")
