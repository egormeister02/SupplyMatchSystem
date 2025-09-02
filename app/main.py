import os
import logging
import asyncio
from datetime import datetime

import pytz
from quart import Quart, request, jsonify
from aiogram import Dispatcher, Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from hypercorn.config import Config
from hypercorn.asyncio import serve

from app.config import config
from app.handlers import register_all_handlers
from app.config.logging import app_logger
from app.services.database import init_db

# Логгер для main.py, используем существующую конфигурацию из app.config.logging
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

# Регистрируем роутеры
register_all_handlers(dp)

@app.before_serving
async def startup():
    """Actions to perform on application startup"""
    app_logger.info("Starting application...")

    # Database schema/init
    try:
        db_ready = await init_db()
        if not db_ready:
            logger.error("Database initialization reported failure")
    except Exception as e:
        logger.error(f"Database initialization exception: {e}")

    # Webhook setup
    webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
    logger.info(f"Setting webhook at: {webhook_url}")

    await bot.delete_webhook()
    await bot.set_webhook(
        url=webhook_url,
        secret_token=getattr(config, 'WEBHOOK_SECRET', None),
        drop_pending_updates=True
    )

    # Set bot commands
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Главное меню")
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