from aiogram import Router, types
from aiogram.filters import Command

# Создаем роутер для базовых команд
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer("Привет! Я бот для поиска поставщиков.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
    Доступные команды:
    /start - Начать работу с ботом
    /help - Показать справку
    """
    await message.answer(help_text)

def register_handlers(dp):
    """Регистрирует все обработчики этого модуля"""
    dp.include_router(router)
