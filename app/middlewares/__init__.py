from aiogram import Dispatcher
from .database import DatabaseMiddleware

def setup_middlewares(dp: Dispatcher):
    """Регистрация всех middleware"""
    # Добавляем middleware базы данных для всех обновлений
    dp.update.middleware(DatabaseMiddleware())
    
    # Здесь можно добавить другие middleware
