"""
Handlers initialization
"""

import importlib
import pkgutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def register_all_handlers(dp):
    """Автоматически находит и регистрирует все модули обработчиков"""
    handlers_dir = Path(__file__).parent
    
    # Перебираем все модули в директории handlers
    for module_info in pkgutil.iter_modules([str(handlers_dir)]):
        if module_info.name == "__init__":
            continue
            
        try:
            # Импортируем модуль
            module = importlib.import_module(f"app.handlers.{module_info.name}")
            
            # Проверяем наличие функции register_handlers
            if hasattr(module, "register_handlers"):
                module.register_handlers(dp)
                logger.info(f"Зарегистрированы обработчики из модуля {module_info.name}")
            else:
                logger.warning(f"Модуль {module_info.name} не имеет функции register_handlers")
                
        except Exception as e:
            logger.error(f"Ошибка при регистрации обработчиков из модуля {module_info.name}: {e}")
