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
from app.handlers import (
    user,
    base,
    actions,
    suppliers,  # Добавляем новый обработчик
    admin  # Добавляем обработчик админского чата
)
from app.middlewares import setup_middlewares
from app.services.database import init_db
#from app.services.storage import s3_service
from app.config.logging import app_logger

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timezone setup
os.environ['TZ'] = config.TIMEZONE
tz = pytz.timezone(config.TIMEZONE)

# Bot and dispatcher initialization
storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Quart application initialization
app = Quart(__name__)

# Register handlers and middleware
def register_handlers():
    base.register_handlers(dp)
    actions.register_handlers(dp)
    user.register_handlers(dp)
    suppliers.register_handlers(dp)  # Регистрируем новый обработчик
    admin.register_handlers(dp)  # Регистрируем обработчики админского чата

register_handlers()  # Вызываем функцию регистрации
setup_middlewares(dp)

@app.before_serving
async def startup():
    """Actions to perform on application startup"""
    app_logger.info("Starting application...")
    
    
    db_ready = await init_db()
    if not db_ready:
        logger.error("Failed to initialize database. Shutting down.")
        os.kill(os.getpid(), signal.SIGTERM)
        return
    
    # Инициализация конфигурации действий
    try:
        from app.config.action_config import update_action_markups
        update_action_markups()
        logger.info("Action config initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize action config: {str(e)}")
    
    # Webhook setup
    webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
    logger.info(f"Setting webhook at: {webhook_url}")
    
    await bot.delete_webhook()
    await bot.set_webhook(
        url=webhook_url,
        secret_token=getattr(config, 'WEBHOOK_SECRET', None)
    )
    
    # Set bot commands
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Главное меню"),
        types.BotCommand(command="/help", description="Помощь")
    ])
    
    logger.info("Application started successfully")

@app.after_serving
async def shutdown():
    """Actions to perform on application shutdown"""
    logger.info("Stopping application...")
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Application stopped")

@app.route(config.WEBHOOK_PATH, methods=['POST'])
async def webhook_handler():
    """Telegram webhook handler"""
    try:
        data = await request.get_json()
        
        # Check secret token in production
        if hasattr(config, 'WEBHOOK_SECRET') and config.WEBHOOK_SECRET:
            secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if secret != config.WEBHOOK_SECRET:
                logger.warning("Request received with invalid secret token")
                return jsonify({'status': 'error', 'message': 'Invalid token'}), 403
        
        # Process Telegram update
        if 'update_id' in data:
            update = types.Update(**data)
            await dp.feed_update(bot=bot, update=update)
            return jsonify({'status': 'ok'})
            
        return jsonify({'status': 'error', 'message': 'Invalid update format'}), 400
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
async def health_check():
    """Endpoint to check application health"""
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
        logger.info("Application terminated by user request")
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")