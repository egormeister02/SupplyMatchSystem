"""
Сервис для отправки сообщений в чат администраторов и обработки их ответов
"""

import logging
import json
import os
from typing import Optional, List, Union, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types.input_file import FSInputFile
from app.config import config
from app.services.local_storage import local_storage_service

logger = logging.getLogger(__name__)

class AdminChatService:
    """
    Сервис для работы с групповым чатом администраторов
    """
    
    def __init__(self):
        """
        Инициализация сервиса
        """
        self.admin_chat_id = config.ADMIN_GROUP_CHAT_ID
    
    @staticmethod
    async def send_message(
        bot: Bot, 
        text: str, 
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        photo: Optional[str] = None,
        document: Optional[str] = None,
        video: Optional[str] = None,
    ) -> Optional[int]:
        """
        Отправляет сообщение в чат администраторов
        
        Args:
            bot: Объект бота
            text: Текст сообщения
            reply_markup: Опциональная клавиатура
            photo: Опциональный путь к фото
            document: Опциональный путь к документу
            video: Опциональный путь к видео
            
        Returns:
            ID сообщения или None в случае ошибки
        """
        if not config.ADMIN_GROUP_CHAT_ID:
            logger.error("ID группового чата администраторов не настроен")
            return None
            
        try:
            # Отправляем сообщение в зависимости от типа контента
            if photo:
                # Проверяем, является ли фото локальным файлом
                if os.path.exists(str(photo)):
                    # Локальный файл - используем FSInputFile
                    message = await bot.send_photo(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        photo=FSInputFile(photo),
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    # Пробуем отправить как URL или ID файла
                    message = await bot.send_photo(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        photo=photo,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
            elif document:
                # Проверяем, является ли документ локальным файлом
                if os.path.exists(str(document)):
                    # Локальный файл - используем FSInputFile
                    message = await bot.send_document(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        document=FSInputFile(document),
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    # Пробуем отправить как URL или ID файла
                    message = await bot.send_document(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        document=document,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
            elif video:
                # Проверяем, является ли видео локальным файлом
                if os.path.exists(str(video)):
                    # Локальный файл - используем FSInputFile
                    message = await bot.send_video(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        video=FSInputFile(video),
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    # Пробуем отправить как URL или ID файла
                    message = await bot.send_video(
                        chat_id=config.ADMIN_GROUP_CHAT_ID,
                        video=video,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
            else:
                message = await bot.send_message(
                    chat_id=config.ADMIN_GROUP_CHAT_ID,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                
            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в чат администраторов: {str(e)}")
            return None
    
    def create_admin_callback_data(self, action: str, **kwargs) -> str:
        """
        Создает callback_data для кнопок админского управления
        
        :param action: Действие (например, approve_supplier, reject_supplier)
        :param kwargs: Дополнительные параметры (например, supplier_id, request_id)
        :return: Encoded callback data
        """
        data = {"action": action, **kwargs}
        callback_data = f"admin:{action}"
        
        # Добавляем дополнительные параметры в callback_data
        for key, value in kwargs.items():
            callback_data += f":{key}={value}"
        
        return callback_data
    
    def parse_admin_callback_data(self, callback_data: str) -> Dict[str, str]:
        """
        Парсит callback_data из формата admin:action:key1=value1:key2=value2
        
        :param callback_data: Строка callback_data
        :return: Словарь с действием и параметрами
        """
        result = {}
        
        # Проверяем, что callback_data начинается с "admin:"
        if not callback_data.startswith("admin:"):
            logger.warning(f"Неверный формат callback_data: {callback_data}")
            return result
        
        # Разбиваем строку на компоненты
        parts = callback_data.split(":")
        
        # Пропускаем префикс "admin" и получаем действие
        if len(parts) > 1:
            result["action"] = parts[1]
        
        # Обрабатываем дополнительные параметры
        for i in range(2, len(parts)):
            try:
                key, value = parts[i].split("=")
                result[key] = value
            except ValueError:
                logger.warning(f"Неверный формат параметра в callback_data: {parts[i]}")
        
        return result
    
    @staticmethod
    async def notify_admins(
        bot: Bot, 
        title: str, 
        message: str, 
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action_buttons: Optional[List[Dict[str, str]]] = None
    ) -> Optional[int]:
        """
        Отправляет уведомление администраторам
        
        Args:
            bot: Объект бота
            title: Заголовок сообщения
            message: Текст сообщения
            user_id: ID пользователя, связанного с уведомлением
            username: Username пользователя
            action_buttons: Список словарей с кнопками действий в формате 
                             [{"text": "Текст кнопки", "callback_data": "admin:action:param=value"}]
                             
        Returns:
            ID сообщения или None в случае ошибки
        """
        text = f"📢 <b>{title}</b>\n\n"
        
        if user_id:
            text += f"👤 Пользователь: ID {user_id}"
            if username:
                text += f" ({username})"
            text += "\n\n"
            
        text += message
        
        # Создаем клавиатуру, если есть кнопки действий
        markup = None
        if action_buttons and len(action_buttons) > 0:
            keyboard = []
            
            # Создаем ряды с кнопками, максимум 2 кнопки в ряду
            row = []
            for button in action_buttons:
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
                
                row.append(InlineKeyboardButton(
                    text=button["text"],
                    callback_data=button["callback_data"]
                ))
                
            if row:  # Добавляем оставшиеся кнопки
                keyboard.append(row)
                
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        return await AdminChatService.send_message(bot, text, reply_markup=markup)
    
    async def send_action_result_to_admin(self, bot: Bot, admin_id: int, text: str, supplier_id: Optional[int] = None) -> bool:
        """
        Отправляет администратору результат выполнения действия
        
        :param bot: Экземпляр бота для отправки сообщения
        :param admin_id: ID администратора
        :param text: Текст сообщения
        :param supplier_id: ID поставщика (опционально)
        :return: True если сообщение отправлено успешно, False иначе
        """
        try:
            message_text = f"🔔 УВЕДОМЛЕНИЕ\n\n{text}"
            
            # Если указан ID поставщика, добавляем его в сообщение
            if supplier_id:
                message_text += f"\n\nID поставщика: {supplier_id}"
            
            await bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="HTML"
            )
            
            logger.info(f"Отправлено уведомление администратору {admin_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке результата действия администратору {admin_id}: {e}")
            return False

    async def notify_admins(self, text: str, keyboard: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Отправляет сообщение всем администраторам в групповой чат
        
        :param text: Текст сообщения
        :param keyboard: Опциональная клавиатура с кнопками
        :return: True если сообщение отправлено успешно, False иначе
        """
        if not self.admin_chat_id:
            logger.warning("Не указан ID чата администраторов, уведомление не отправлено")
            return False
        
        try:
            # Этот метод должен использовать Bot, который передается 
            # как аргумент при вызове из хендлеров
            # Здесь не инициализируем Bot, чтобы не создавать дублирование
            logger.info(f"Подготовлено сообщение для админского чата: {text[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Ошибка при подготовке уведомления администраторам: {e}")
            return False
    
    async def send_supplier_to_admin_chat(self, bot: Bot, supplier_id: int, supplier_data: Dict[str, Any], **kwargs) -> bool:
        """
        Отправляет карточку поставщика в чат администраторов с кнопкой "Забрать себе"
        
        :param bot: Экземпляр бота для отправки сообщения
        :param supplier_id: ID поставщика
        :param supplier_data: Данные поставщика
        :param kwargs: Дополнительные параметры для обратной совместимости
        :return: True если сообщение отправлено успешно, False иначе
        """
        # Проверяем настройку ID чата администраторов
        if not self.admin_chat_id:
            logger.error("ID чата администраторов (ADMIN_GROUP_CHAT_ID) не настроен в конфигурации!")
            logger.error("Используйте команду /chatid в нужном чате для получения ID")
            return False
        
        # Логируем информацию о попытке отправки сообщения
        logger.info(f"Попытка отправки сообщения о поставщике {supplier_id} в чат {self.admin_chat_id}")
        
        try:
            # Формируем текст сообщения с основной информацией о поставщике
            company_name = supplier_data.get('company_name', 'Название не указано')
            product_name = supplier_data.get('product_name', "")
            category = supplier_data.get('category_name', "")
            subcategory = supplier_data.get('subcategory_name', "")
            description = supplier_data.get('description', 'Описание отсутствует')
            photos = supplier_data.get('photos', [])
            
            message_text = (
                f"📋 НОВЫЙ ПОСТАВЩИК\n\n"
                f"🏢 Компания: {company_name}\n"
                f"🔍 Категория: {category}\n"
                f"🔍 Подкатегория: {subcategory}\n"
                f"🔍 Наименование продукта: {product_name}\n"
                f"📝 Описание: {description[:200]}{'...' if len(description) > 200 else ''}"
            )
            
            # Инициализируем переменную для пути к фото
            photo_path = None
            
            # Берем первую фотографию только если список не пуст
            if photos and len(photos) > 0:
                first_photo = photos[0]
                
                # Определяем путь к фотографии в зависимости от формата данных
                if isinstance(first_photo, dict):
                    if 'storage_path' in first_photo:
                        photo_path = first_photo['storage_path']
                    elif 'file_path' in first_photo:
                        photo_path = first_photo['file_path']
                else:
                    photo_path = first_photo
            
            # Создаем клавиатуру с кнопкой "Забрать себе"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📥 Забрать себе на проверку", 
                            callback_data=self.create_admin_callback_data(
                                "take_supplier", 
                                supplier_id=supplier_id
                            )
                        )
                    ]
                ]
            )
            
            # Пытаемся получить полный путь к файлу фотографии, если она есть
            input_photo = None
            if photo_path:
                try:
                    # Если путь является существующим файлом, используем его
                    if os.path.exists(str(photo_path)):
                        input_photo = FSInputFile(photo_path)
                    else:
                        # Пробуем получить полный путь через сервис хранения
                        full_path = await local_storage_service.get_file_path(str(photo_path))
                        if full_path and os.path.exists(full_path):
                            input_photo = FSInputFile(full_path)
                        else:
                            # Если не найден полный путь, пытаемся использовать как URL
                            input_photo = photo_path
                except Exception as e:
                    logger.error(f"Ошибка при подготовке фото: {e}")
                    input_photo = None
            
            # Отправляем сообщение с фото или без в зависимости от наличия фото
            try:
                if input_photo:
                    message = await bot.send_photo(
                        chat_id=self.admin_chat_id,
                        photo=input_photo,
                        caption=message_text,
                        reply_markup=keyboard
                    )
                else:
                    message = await bot.send_message(
                        chat_id=self.admin_chat_id,
                        text=message_text,
                        reply_markup=keyboard
                    )
                
                logger.info(f"Отправлено сообщение о новом поставщике {supplier_id} в чат администраторов")
                return True
                
            except Exception as send_error:
                logger.error(f"Ошибка при отправке сообщения: {send_error}")
                
                # Пробуем отправить только текст, если отправка с фото не удалась
                if input_photo:
                    try:
                        await bot.send_message(
                            chat_id=self.admin_chat_id,
                            text=message_text,
                            reply_markup=keyboard
                        )
                        logger.info(f"Отправлено текстовое сообщение о поставщике {supplier_id} (без фото)")
                        return True
                    except Exception as text_error:
                        logger.error(f"Не удалось отправить текстовое сообщение: {text_error}")
                        return False
                else:
                    return False
            
        except Exception as e:
            logger.error(f"Ошибка при отправке карточки поставщика в чат администраторов: {e}")
            return False

    async def send_request_to_admin_chat(self, bot: Bot, request_id: int, request_data: Dict[str, Any], **kwargs) -> bool:
        """
        Отправляет карточку заявки в чат администраторов
        """
        try:
            if not self.admin_chat_id:
                logger.error("Идентификатор чата администраторов не задан")
                return False
            
            # Получаем категорию заявки
            category_id = request_data.get("category_id")
            category_name = request_data.get("category_name", "Не указана")
            
            # Получаем дату создания заявки
            created_at = request_data.get("created_at")
            created_at_str = ""
            if created_at:
                if isinstance(created_at, str):
                    try:
                        from datetime import datetime
                        created_at_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at_str = created_at_dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        created_at_str = created_at
                else:
                    created_at_str = str(created_at)
            
            # Формируем текст сообщения с описанием заявки
            message_text = f"📝 <b>Новая заявка #{request_id}</b>\n\n"
            
            message_text += f"<b>Категория:</b> {category_name}\n\n"
            
            # Добавляем описание, если есть
            description = request_data.get("description", "").strip()
            if description:
                message_text += f"<b>Описание:</b>\n{description}\n\n"
            
            # Добавляем контактную информацию
            contact_info = request_data.get("contact_info", "").strip()
            if contact_info:
                message_text += f"<b>Контакты:</b>\n{contact_info}\n\n"
            
            # Добавляем дату создания
            if created_at_str:
                message_text += f"<b>Создано:</b> {created_at_str}\n"
            
            # Получаем медиа-файлы заявки
            photos = request_data.get("photos", [])
            video = request_data.get("video")
            
            # Создаем клавиатуру с кнопкой "Забрать себе"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📥 Забрать себе на проверку", 
                            callback_data=self.create_admin_callback_data(
                                "take_request", 
                                request_id=request_id
                            )
                        )
                    ]
                ]
            )

            try:
                # Если есть фото, отправляем его с текстом
                if photos and len(photos) > 0:
                    # Пробуем получить путь к первому фото
                    photo_path = None
                    first_photo = photos[0]
                    
                    if isinstance(first_photo, dict):
                        if 'file_path' in first_photo:
                            photo_path = first_photo['file_path']
                        elif 'storage_path' in first_photo:
                            photo_path = first_photo['storage_path']
                    
                    if photo_path:
                        try:
                            full_path = await local_storage_service.get_file_path(str(photo_path))
                            if full_path and os.path.exists(full_path):
                                await bot.send_photo(
                                    chat_id=self.admin_chat_id,
                                    photo=FSInputFile(full_path),
                                    caption=message_text,
                                    reply_markup=keyboard,
                                    parse_mode="HTML"
                                )
                                logger.info(f"Отправлено сообщение с фото о заявке {request_id}")
                                return True
                        except Exception as photo_error:
                            logger.error(f"Ошибка при отправке сообщения с фото: {photo_error}")
                            # Продолжаем и попробуем отправить только текст
                
                # Если не удалось отправить фото или его нет, отправляем только текст
                await bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                logger.info(f"Отправлено текстовое сообщение о заявке {request_id}")
                return True
            except Exception as text_error:
                logger.error(f"Не удалось отправить текстовое сообщение: {text_error}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отправке карточки заявки в чат администраторов: {e}")
            return False

# Создаем единственный экземпляр сервиса
admin_chat_service = AdminChatService()
