import logging
import sys
import os
from pathlib import Path

# Создаем директорию для логов, если её нет
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Формат логов
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Определяем режим работы (разработка или продакшен)
is_development = os.getenv("APP_ENV", "development").lower() == "development"

# Проверка, были ли обработчики уже настроены
root_logger = logging.getLogger()

# Очистим все имеющиеся обработчики, чтобы избежать дублирования
if root_logger.handlers:
    root_logger.handlers.clear()

# Устанавливаем уровень логирования в зависимости от режима
root_logger.setLevel(logging.DEBUG if is_development else logging.INFO)

# Обработчик для вывода в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG if is_development else logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(console_handler)

# Обработчик для записи в файл
file_handler = logging.FileHandler(log_dir / "app.log")
file_handler.setLevel(logging.DEBUG if is_development else logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(file_handler)

# Настройка логгера для базы данных
db_logger = logging.getLogger("sqlalchemy.engine")
db_logger.setLevel(logging.INFO)
# В режиме разработки логи базы данных будут отображаться
db_logger.propagate = not is_development

# Настройка логгера для aiogram
aiogram_logger = logging.getLogger("aiogram")
aiogram_logger.setLevel(logging.INFO if is_development else logging.WARNING)
# В режиме разработки логи aiogram будут отображаться
aiogram_logger.propagate = is_development

# Настройка логгера для нашего приложения
app_logger = logging.getLogger("app")
app_logger.setLevel(logging.DEBUG if is_development else logging.INFO)
# Логи нашего приложения всегда должны отображаться
app_logger.propagate = True

# Функция для переключения режима логирования
def set_debug_mode(debug=True):
    """
    Переключает уровень логирования между DEBUG и INFO
    
    Args:
        debug (bool): True - для режима отладки, False - для продакшена
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Обновляем уровни логирования
    root_logger.setLevel(level)
    console_handler.setLevel(level)
    file_handler.setLevel(level)
    app_logger.setLevel(level)
    
    # Настраиваем propagate для разных логгеров
    db_logger.propagate = debug
    aiogram_logger.propagate = debug
    
    app_logger.info(f"Уровень логирования установлен на {'DEBUG' if debug else 'INFO'}") 