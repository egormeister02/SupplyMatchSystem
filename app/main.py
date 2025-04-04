import os
import logging
import asyncio
from datetime import datetime
import signal

import pytz
from quart import Quart, request, jsonify
from aiogram import Dispatcher, Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from hypercorn.config import Config
from hypercorn.asyncio import serve

from app.config import config
from app.handlers import register_all_handlers
from app.middlewares import setup_middlewares
from app.services.database import init_db
#from app.services.storage import s3_service

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Установка часового пояса
os.environ['TZ'] = config.TIMEZONE
tz = pytz.timezone(config.TIMEZONE)

# Инициализация бота и диспетчера
storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Инициализация приложения Quart
app = Quart(__name__)

# Регистрация обработчиков и middleware
register_all_handlers(dp)
setup_middlewares(dp)

@app.before_serving
async def startup():
    """Действия при запуске приложения"""
    logger.info("Запуск приложения...")
    
    # Инициализация БД
    db_ready = await init_db()
    if not db_ready:
        logger.error("Не удалось инициализировать базу данных. Завершаем работу.")
        os.kill(os.getpid(), signal.SIGTERM)
        return
    
    # Настройка вебхука
    webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
    logger.info(f"Устанавливаем вебхук по адресу: {webhook_url}")
    
    await bot.delete_webhook()
    await bot.set_webhook(
        url=webhook_url,
        secret_token=getattr(config, 'WEBHOOK_SECRET', None)
    )
    
    # Установка команд бота
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Главное меню"),
        types.BotCommand(command="/help", description="Помощь")
    ])
    
    logger.info("Приложение успешно запущено")

@app.after_serving
async def shutdown():
    """Действия при остановке приложения"""
    logger.info("Остановка приложения...")
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Приложение остановлено")

@app.route(config.WEBHOOK_PATH, methods=['POST'])
async def webhook_handler():
    """Обработчик вебхуков от Telegram"""
    try:
        data = await request.get_json()
        
        # Проверка секретного токена в продакшене
        if hasattr(config, 'WEBHOOK_SECRET') and config.WEBHOOK_SECRET:
            secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if secret != config.WEBHOOK_SECRET:
                logger.warning("Получен запрос с неверным секретным токеном")
                return jsonify({'status': 'error', 'message': 'Invalid token'}), 403
        
        # Обработка обновления от Telegram
        if 'update_id' in data:
            update = types.Update(**data)
            await dp.feed_update(bot=bot, update=update)
            return jsonify({'status': 'ok'})
            
        return jsonify({'status': 'error', 'message': 'Invalid update format'}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
async def health_check():
    """Эндпоинт для проверки работоспособности приложения"""
    return jsonify({
        'status': 'ok', 
        'timestamp': datetime.now(tz).isoformat(),
        'env': os.getenv("APP_ENV", "local")
    })

if __name__ == '__main__':
    hypercorn_config = Config()
    hypercorn_config.bind = [f"{config.HOST}:{config.PORT}"]
    hypercorn_config.loglevel = config.LOG_LEVEL.lower()
    
    async def run():
        await serve(app, hypercorn_config)
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Приложение завершено по запросу пользователя")
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {str(e)}")