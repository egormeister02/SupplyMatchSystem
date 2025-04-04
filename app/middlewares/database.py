from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.services.database import AsyncSessionLocal

class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Создаем сессию для каждого запроса
        async with AsyncSessionLocal() as session:
            # Добавляем сессию в данные, которые будут доступны обработчикам
            data["session"] = session
            
            # Пробуем выполнить обработчик
            try:
                return await handler(event, data)
            except Exception as e:
                # В случае ошибки откатываем изменения
                await session.rollback()
                raise
            finally:
                # В любом случае закрываем сессию
                await session.close()
