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
    
    # Определяем порядок загрузки модулей
    # Изменяем порядок: модуль requests должен загружаться ПЕРЕД suppliers
    module_order = ["user", "base", "actions", "requests", "suppliers", "my_suppliers", "my_requests", "admin", "file_handler", "matches", "write_review", "reports", "help"]
    
    # Сначала регистрируем модули в определенном порядке
    for module_name in module_order:
        try:
            # Импортируем модуль
            module = importlib.import_module(f"app.handlers.{module_name}")
            
            # Проверяем наличие функции register_handlers
            if hasattr(module, "register_handlers"):
                module.register_handlers(dp)
                logger.info(f"Зарегистрированы обработчики из модуля {module_name}")
            else:
                logger.warning(f"Модуль {module_name} не имеет функции register_handlers")
                
        except Exception as e:
            logger.error(f"Ошибка при регистрации обработчиков из модуля {module_name}: {e}")
    
    # Затем регистрируем все остальные модули, которые могут быть добавлены позже
    for module_info in pkgutil.iter_modules([str(handlers_dir)]):
        if module_info.name == "__init__" or module_info.name in module_order:
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
