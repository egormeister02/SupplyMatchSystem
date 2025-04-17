"""
Utility functions for message operations
"""

from typing import Union, Optional
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.types.input_file import FSInputFile
from aiogram.types import InputMediaPhoto, InputMediaVideo
from aiogram.exceptions import TelegramAPIError
import logging
import os
from app.services.local_storage import local_storage_service
from app.services import get_db_session, DBService

# Вспомогательная функция для получения имени администратора по ID
async def get_admin_username(admin_id):
    """
    Получает username администратора по его ID
    
    Args:
        admin_id: ID администратора
        
    Returns:
        str: Username администратора или его ID как строка
    """
    try:
        async with get_db_session() as session:
            db_service = DBService(session)
            user_data = await db_service.get_user_by_id(admin_id)
            
            if user_data:
                if user_data.get("username"):
                    return f"{user_data.get('username')} (ID:{admin_id})"
                else:
                    first_name = user_data.get("first_name", "")
                    last_name = user_data.get("last_name", "")
                    full_name = f"{first_name} {last_name}".strip()
                    return f"{full_name if full_name else 'Администратор'} (ID:{admin_id})"
            return f"ID:{admin_id}"
    except Exception as e:
        logging.error(f"Ошибка при получении данных администратора: {e}")
        return f"ID:{admin_id}"

async def remove_previous_keyboard(
    bot: Bot, 
    message_id: int, 
    chat_id: int
) -> bool:
    """
    Remove inline keyboard from a previously sent message
    
    Args:
        bot (Bot): Bot instance
        message_id (int): ID of the message with keyboard to remove
        chat_id (int): ID of the chat with the message
        
    Returns:
        bool: True if keyboard was removed successfully, False otherwise
    """
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
        return True
    except TelegramAPIError:
        # Message can't be edited or already has no keyboard
        return False

async def remove_keyboard_from_context(
    bot: Bot, 
    event: Union[Message, CallbackQuery], 
    message_id: Optional[int] = None
) -> bool:
    """
    Remove keyboard from a message using context from Message or CallbackQuery
    
    Args:
        bot (Bot): Bot instance
        event (Union[Message, CallbackQuery]): Message or callback query with context data
        message_id (Optional[int]): Optional message ID override. If not provided:
            - For CallbackQuery: uses message_id from callback query
            - For Message: uses message_id-1 (assumes previous message)
            
    Returns:
        bool: True if keyboard was removed successfully, False otherwise
    """
    if isinstance(event, CallbackQuery):
        chat_id = event.message.chat.id
        msg_id = message_id or event.message.message_id
    else:  # Message
        chat_id = event.chat.id
        # If message_id not provided, use previous message (current-1)
        msg_id = message_id or (event.message_id - 1)
    
    return await remove_previous_keyboard(bot, msg_id, chat_id)

async def edit_message_text_and_keyboard(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None
) -> bool:
    """
    Edit both text and keyboard of a message
    
    Args:
        bot (Bot): Bot instance
        chat_id (int): ID of the chat with the message
        message_id (int): ID of the message to edit
        text (str): New text for the message
        reply_markup: New keyboard markup (or None to remove keyboard)
        
    Returns:
        bool: True if message was edited successfully, False otherwise
    """
    # Проверяем тип клавиатуры - можно редактировать только InlineKeyboardMarkup
    if isinstance(reply_markup, ReplyKeyboardMarkup):
        return False  # Нельзя редактировать сообщение с ReplyKeyboardMarkup
        
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        return True
    except TelegramAPIError as e:
        # Логируем ошибку для отладки
        logging.error(f"Error editing message: {e}")
        # Message can't be edited or hasn't changed
        return False 
    

async def send_supplier_card(
    bot: Bot,
    chat_id: int, 
    supplier: dict, 
    keyboard: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None, 
    message_id: Optional[int] = None,
    include_video: bool = True,  # Параметр для включения видео в группу
    show_status: bool = False    # Параметр для отображения статуса поставщика
) -> dict:
    """
    Отправляет или редактирует карточку поставщика в указанный чат.
    
    Args:
        bot (Bot): Объект бота для отправки сообщений
        chat_id (int): ID чата для отправки
        supplier (dict): Словарь с данными о поставщике
        keyboard (Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]]): Клавиатура для сообщения
        message_id (Optional[int]): ID сообщения для редактирования (если None, то отправляется новое)
        include_video (bool): Включать ли видео в медиа-группу (если True и есть несколько фото)
        show_status (bool): Показывать ли статус поставщика
        
    Returns:
        dict: Словарь с message_ids всех отправленных сообщений:
            - keyboard_message_id: ID сообщения с клавиатурой
            - media_message_ids: список ID сообщений медиагруппы или ID сообщения с фото
    """
    # Формируем текст сообщения
    # Формируем заголовок
    title = f"Название: {supplier.get('company_name')}"
    
    # Категория и подкатегория
    category_info = []
    if supplier.get('main_category_name'):
        category_info.append(supplier.get('main_category_name'))
    if supplier.get('category_name'):
        category_info.append(supplier.get('category_name'))
    
    category_text = " > ".join(category_info) if category_info else "Не указана"
    
    # Описание
    description = supplier.get('description', 'Не указано')
    
    # Местоположение
    location_parts = []
    if supplier.get('country'):
        location_parts.append(supplier.get('country'))
    if supplier.get('region'):
        location_parts.append(supplier.get('region'))
    if supplier.get('city'):
        location_parts.append(supplier.get('city'))
    if supplier.get('address'):
        location_parts.append(supplier.get('address'))
    
    location = ", ".join(location_parts) if location_parts else "Не указано"
    
    # Контактная информация
    contacts = []
    if supplier.get('contact_username'):
        contacts.append(f"Telegram: {supplier.get('contact_username')}")
    if supplier.get('contact_phone'):
        contacts.append(f"Телефон: {supplier.get('contact_phone')}")
    if supplier.get('contact_email'):
        contacts.append(f"Email: {supplier.get('contact_email')}")
    
    contact_info = "\n".join(contacts) if contacts else "Контактная информация не указана"
    
    # Фотографии и видео
    photos = supplier.get('photos', [])
    video = supplier.get('video')
    
    # Добавляем подробное логирование для отладки видео
    logging.info(f"Данные по медиа поставщика {supplier.get('id')}:")
    logging.info(f"Фотографии: {len(photos) if photos else 0} шт.")
    logging.info(f"Наличие видео: {video is not None}")
    if video:
        logging.info(f"Подробные данные видео: {video}")
    
    media_info = []
    if photos:
        media_info.append(f"Фотографий: {len(photos)}")
    if video:
        media_info.append("Видео: имеется")
    
    media_text = ", ".join(media_info) if media_info else "Медиа: отсутствуют"
    
    # Собираем полный текст сообщения
    text = f"{title}\n\n"
    text += f"Категория: {category_text}\n"
    text += f"Продукт/услуга: {supplier.get('product_name', 'Не указан')}\n\n"
    text += f"Описание:\n{description}\n\n"
    text += f"Местоположение: {location}\n\n"
    text += f"Контакты:\n{contact_info}\n\n"
    text += f"{media_text}"
    
    # Добавляем информацию о статусе поставщика, если запрошено
    if show_status:
        status = supplier.get('status', 'pending')
        status_emoji = "✅" if status == "approved" else "❌" if status == "rejected" else "⏳"
        status_text = "Одобрен" if status == "approved" else "Отклонен" if status == "rejected" else "На проверке"
        text += f"\n\nСтатус: {status_emoji} {status_text}"
        
        # Если поставщик отклонен и есть причина отклонения, показываем её
        if status == "rejected" and supplier.get("rejection_reason"):
            text += f"\n\n❗ Причина отклонения: {supplier.get('rejection_reason')}"
    
    logging.info(f"Фотографии поставщика: {photos}")
    
    # Получаем пути ко всем фотографиям
    photo_paths = []
    for photo in photos:
        relative_path = photo.get('file_path')
        if relative_path:
            try:
                full_path = await local_storage_service.get_file_path(relative_path)
                if full_path and os.path.exists(full_path):
                    photo_paths.append(full_path)
            except Exception as e:
                logging.error(f"Ошибка при получении пути к фото: {e}")
    
    # Получаем путь к видео, если оно есть
    video_path = None
    if video and include_video:
        video_info = video
        logging.info(f"Начинаем обработку видео: {video_info}")
        if isinstance(video_info, dict):
            relative_path = video_info.get('storage_path')
            if not relative_path:
                relative_path = video_info.get('file_path')
            logging.info(f"Относительный путь к видео: {relative_path}")
            if relative_path:
                try:
                    video_path = await local_storage_service.get_file_path(relative_path)
                    logging.info(f"Полный путь к видео: {video_path}")
                    if not video_path or not os.path.exists(video_path):
                        logging.error(f"Видеофайл не найден по пути {video_path}")
                        video_path = None
                except Exception as e:
                    logging.error(f"Ошибка при получении пути к видео: {e}")
                    video_path = None
    
    logging.info(f"Итоговый путь к видео: {video_path}")
    logging.info(f"Видео будет включено в группу: {include_video and video_path is not None}")
    
    # Если есть message_id и нет фото и видео, то редактируем текстовое сообщение
    if message_id and not photo_paths and not video_path:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard
            )
            return {"keyboard_message_id": message_id, "media_message_ids": []}
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            # Если не удалось отредактировать, отправляем новое
            message_id = None
    
    # Если фотографий больше одной или есть фото и видео, отправляем их группой
    if len(photo_paths) > 1 or (photo_paths and video_path and include_video):
        logging.info(f"Отправляем медиа-группу. Фото: {len(photo_paths)}, Видео: {video_path is not None}")
        # Если был message_id, удаляем старое сообщение
        if message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения: {e}")
        
        try:
            # Создаем список медиа-объектов
            media = []
            
            # Добавляем все фотографии
            for i, photo_path in enumerate(photo_paths):
                # Для первой фотографии добавляем подпись, если нет видео
                # Если есть видео, добавим подпись к нему (оно будет последним)
                caption = text if (i == 0 and not video_path) else None
                media.append(InputMediaPhoto(
                    media=FSInputFile(photo_path),
                    caption=caption
                ))
            
            # Добавляем видео в конец группы, если оно есть
            if video_path and include_video:
                logging.info(f"Добавляем видео в медиа-группу: {video_path}")
                # Если мы добавляем видео последним, то подпись идет на нем
                # Удаляем подпись с первого фото
                if len(media) > 0:
                    media[0].caption = None
                
                media.append(InputMediaVideo(
                    media=FSInputFile(video_path),
                    caption=text
                ))
                logging.info("Видео успешно добавлено в медиа-группу")
            
            # Отправляем медиа-группу
            media_messages = await bot.send_media_group(
                chat_id=chat_id,
                media=media
            )
            
            # Сохраняем ID всех сообщений медиагруппы
            media_message_ids = [msg.message_id for msg in media_messages]
            
            # Для медиагруппы отправляем клавиатуру отдельным сообщением
            if keyboard:
                keyboard_message = await bot.send_message(
                    chat_id=chat_id,
                    text="Используйте кнопки для навигации:",
                    reply_markup=keyboard
                )
                return {
                    "keyboard_message_id": keyboard_message.message_id,
                    "media_message_ids": media_message_ids
                }
            else:
                return {
                    "keyboard_message_id": None,
                    "media_message_ids": media_message_ids
                }
                
        except Exception as e:
            logging.error(f"Ошибка при отправке медиа-группы: {e}")
            # Если не удалось отправить медиа, отправляем просто текст
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard
            )
            return {
                "keyboard_message_id": msg.message_id,
                "media_message_ids": []
            }
    # Если есть только одна фотография, отправляем её с текстом и клавиатурой
    elif len(photo_paths) == 1:
        # Если был message_id, удаляем старое сообщение
        if message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения: {e}")
        
        try:
            # Отправляем одно фото с текстом и клавиатурой
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(photo_paths[0]),
                caption=text,
                reply_markup=keyboard
            )
            return {
                "keyboard_message_id": message.message_id,
                "media_message_ids": [message.message_id]
            }
        except Exception as e:
            logging.error(f"Ошибка при отправке фотографии: {e}")
            # Если не удалось отправить фото, отправляем просто текст
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard
            )
            return {
                "keyboard_message_id": msg.message_id,
                "media_message_ids": []
            }
    # Если есть только видео, отправляем его с текстом и клавиатурой
    elif video_path:
        logging.info(f"Отправляем только видео: {video_path}")
        # Если был message_id, удаляем старое сообщение
        if message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения: {e}")
        
        try:
            # Отправляем одно видео с текстом и клавиатурой
            message = await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(video_path),
                caption=text,
                reply_markup=keyboard
            )
            return {
                "keyboard_message_id": message.message_id,
                "media_message_ids": [message.message_id]
            }
        except Exception as e:
            logging.error(f"Ошибка при отправке видео: {e}")
            # Выводим трассировку ошибки для отладки
            import traceback
            logging.error(f"Трассировка: {traceback.format_exc()}")
            # Если не удалось отправить видео, отправляем просто текст
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard
            )
            return {
                "keyboard_message_id": msg.message_id,
                "media_message_ids": []
            }
    else:
        # Если нет фото и видео, отправляем текстовое сообщение с клавиатурой
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard  # Прикрепляем клавиатуру сразу к сообщению
        )
        return {
            "keyboard_message_id": message.message_id,
            "media_message_ids": []
        }
    
    return {
        "keyboard_message_id": None,
        "media_message_ids": []
    } 