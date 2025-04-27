"""
Сервис для управления очередью уведомлений поставщикам
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Awaitable, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.local_storage import local_storage_service
from app.services.database import DBService, get_db_session
import os
from app.utils.message_utils import send_request_card

logger = logging.getLogger(__name__)

class NotificationQueue:
    """
    Класс для управления асинхронной очередью уведомлений поставщикам
    """
    def __init__(self):
        """Инициализация сервиса очереди уведомлений"""
        self._queue = asyncio.Queue()
        self._worker_task = None
        self._processing = False
        self._retry_delay = 10  # Задержка перед повторной попыткой в секундах
        self._max_retries = 3   # Максимальное количество попыток отправки
    
    async def start(self, bot: Bot):
        """Запускает обработчик очереди уведомлений"""
        if self._worker_task is None or self._worker_task.done():
            self._processing = True
            self._worker_task = asyncio.create_task(self._process_queue(bot))
            logger.info("Запущен обработчик очереди уведомлений")
    
    async def stop(self):
        """Останавливает обработчик очереди уведомлений"""
        if self._worker_task and not self._worker_task.done():
            self._processing = False
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Остановлен обработчик очереди уведомлений")
    
    async def add_supplier_notifications(
        self, 
        bot: Bot, 
        request_id: int, 
        matches: List[Dict[str, Any]],
        request_data: Optional[Dict[str, Any]] = None
    ):
        """
        Добавляет уведомления поставщикам о новой заявке в очередь
        
        Args:
            bot: Объект бота для отправки уведомлений
            request_id: ID заявки
            matches: Список словарей с информацией о созданных matches и поставщиках
            request_data: Данные заявки (опционально, если не указано - будут получены из БД)
        """
        if not matches:
            logger.warning(f"Нет подходящих поставщиков для уведомления о заявке {request_id}")
            return
        
        # Если данные заявки не предоставлены, получаем их из БД
        if not request_data:
            request_data = await DBService.get_request_by_id_static(request_id)
            if not request_data:
                logger.error(f"Не удалось получить данные заявки {request_id} для отправки уведомлений")
                return
        
        # Запускаем обработчик очереди
        if not self._processing:
            await self.start(bot)
        
        # Добавляем задачи в очередь
        logger.info(f"Добавление {len(matches)} уведомлений в очередь для заявки {request_id}")
        for match_info in matches:
            notification_task = {
                "type": "supplier_request_notification",
                "user_id": match_info["user_id"],
                "match_id": match_info["match_id"],
                "supplier_id": match_info["supplier_id"],
                "request_id": request_id,
                "request_data": request_data,
                "retries": 0
            }
            await self._queue.put(notification_task)
        
        logger.info(f"Добавлено {len(matches)} уведомлений в очередь для заявки {request_id}")
        
    async def _process_queue(self, bot: Bot):
        """
        Процесс обработки очереди уведомлений
        
        Args:
            bot: Объект бота для отправки уведомлений
        """
        logger.info("Начата обработка очереди уведомлений")
        
        while self._processing:
            try:
                # Получаем задачу из очереди
                task = await self._queue.get()
                
                try:
                    # Обрабатываем уведомление в зависимости от типа
                    if task["type"] == "supplier_request_notification":
                        await self._send_supplier_request_notification(bot, task)
                    else:
                        logger.warning(f"Неизвестный тип уведомления: {task['type']}")
                
                except Exception as e:
                    # В случае ошибки, пробуем еще раз, если не превышен лимит попыток
                    logger.error(f"Ошибка при отправке уведомления: {e}")
                    
                    if task["retries"] < self._max_retries:
                        task["retries"] += 1
                        logger.info(f"Повторная попытка {task['retries']}/{self._max_retries} через {self._retry_delay} сек.")
                        await asyncio.sleep(self._retry_delay)
                        await self._queue.put(task)
                    else:
                        logger.error(f"Не удалось отправить уведомление после {self._max_retries} попыток")
                
                finally:
                    # Отмечаем задачу как выполненную
                    self._queue.task_done()
            
            except asyncio.CancelledError:
                # Обработчик остановлен
                break
            
            except Exception as e:
                # Неожиданная ошибка в обработчике
                logger.error(f"Неожиданная ошибка в обработчике очереди: {e}")
                await asyncio.sleep(1)  # Небольшая пауза, чтобы не перегружать систему
        
        logger.info("Обработчик очереди уведомлений остановлен")
    
    async def _send_supplier_request_notification(self, bot: Bot, task: Dict[str, Any]):
        """
        Отправляет уведомление поставщику о новой заявке
        
        Args:
            bot: Объект бота для отправки уведомлений
            task: Словарь с данными задачи
        """
        user_id = task["user_id"]
        match_id = task["match_id"]
        supplier_id = task["supplier_id"]
        request_id = task["request_id"]
        request_data = task["request_data"]
        
        logger.info(f"Отправка уведомления пользователю {user_id} о заявке {request_id}")
        
        # Создаем клавиатуру с кнопками для принятия/отклонения заявки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять заявку",
                        callback_data=f"match:accept:{match_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"match:reject:{match_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔍 Подробности",
                        callback_data=f"match:details:{match_id}"
                    )
                ]
            ]
        )
        
        try:
            # Используем готовую функцию для отправки карточки заявки
            message = await send_request_card(
                bot=bot,
                chat_id=user_id,
                request=request_data,
                keyboard=keyboard,
                include_video=True,  # Включаем видео в группу
                show_status=False     # Не показываем статус заявки
            )
            
            if message:
                logger.info(f"Отправлено уведомление пользователю {user_id} о заявке {request_id}")
            else:
                logger.warning(f"Не удалось отправить карточку заявки пользователю {user_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            raise

# Создаем единственный экземпляр сервиса
notification_queue_service = NotificationQueue() 