"""
Utility functions for message operations
"""

from typing import Union, Optional
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError
import logging
import os

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
    inline_keyboard: Optional[InlineKeyboardMarkup] = None, 
    message_id: Optional[int] = None
) -> None:
    """
    Отправляет или редактирует карточку поставщика в указанный чат.
    
    Args:
        bot (Bot): Объект бота для отправки сообщений
        chat_id (int): ID чата для отправки
        supplier (dict): Словарь с данными о поставщике
        inline_keyboard (Optional[InlineKeyboardMarkup]): Клавиатура для сообщения
        message_id (Optional[int]): ID сообщения для редактирования (если None, то отправляется новое)
    """
    from aiogram.types import InputMediaPhoto
    
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
    
    # Получаем путь к главному фото
    photo_path = None
    if photos and len(photos) > 0:
        photo_path = photos[0].get('file_path')
    
    # Если есть message_id, то редактируем сообщение
    if message_id:
        try:
            if photo_path and os.path.exists(photo_path):
                # Редактируем фото и текст
                media = InputMediaPhoto(media=photo_path, caption=text)
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=media,
                    reply_markup=inline_keyboard
                )
            else:
                # Редактируем только текст
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=inline_keyboard
                )
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            # Если не удалось отредактировать, отправляем новое
            message_id = None
    
    # Если нет message_id или не удалось отредактировать, отправляем новое сообщение
    if not message_id:
        if photo_path and os.path.exists(photo_path):
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_path,
                caption=text,
                reply_markup=inline_keyboard
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=inline_keyboard
            ) 