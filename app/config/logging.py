import logging
import sys
from pathlib import Path

# Создаем директорию для логов, если её нет
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Формат логов
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Обработчик для вывода в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(console_handler)

# Обработчик для записи в файл
file_handler = logging.FileHandler(log_dir / "app.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format))
root_logger.addHandler(file_handler)

# Настройка логгера для базы данных
db_logger = logging.getLogger("sqlalchemy.engine")
db_logger.setLevel(logging.INFO)

# Настройка логгера для aiogram
aiogram_logger = logging.getLogger("aiogram")
aiogram_logger.setLevel(logging.INFO)

# Настройка логгера для нашего приложения
app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO) 