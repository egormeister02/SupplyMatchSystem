from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from app.bot import bot
import logging
logger = logging.getLogger(__name__)
router = Router()

async def delete_message_reply_markup(message: types.Message):
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id - 1,
            reply_markup=None
        )
    except Exception as e:
        logger.debug(f"Could not delete message reply markup: {str(e)}")
        # Silently ignore the error as it's not critical

    
@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в систему управления производством!\n\n"
        "Пожалуйста, выберите вашу должность из списка ниже:"
    )

