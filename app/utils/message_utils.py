"""
Utility functions for message operations
"""

from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
import logging

logger = logging.getLogger(__name__)

async def send_joke_message(message: types.Message, joke_text: str, users_jokes_id: int | None):
    """
    Отправляет анекдот пользователю с кнопками лайк/дизлайк, сменить тему и следующий.
    """
    logger.info(f"Sending joke message: users_jokes_id={users_jokes_id}, joke_text='{joke_text[:50]}...'")
    
    # Проверяем типы
    if users_jokes_id is not None and (not isinstance(users_jokes_id, int) or users_jokes_id <= 0):
        logger.error(f"Invalid users_jokes_id type in send_joke_message: {type(users_jokes_id)}, value: {users_jokes_id}")
        users_jokes_id = None
    
    formatted_message = f"{joke_text}"
    sent_message = await message.answer(formatted_message)
    
    # Создаем начальную клавиатуру в состоянии "full"
    keyboard = await create_dynamic_keyboard(users_jokes_id, sent_message.message_id, "full")
    await sent_message.edit_reply_markup(reply_markup=keyboard)

async def remove_keyboard_from_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Удаляет inline клавиатуру у сообщения
    
    Args:
        bot (Bot): Объект бота
        chat_id (int): ID чата
        message_id (int): ID сообщения
        
    Returns:
        bool: True если клавиатура была удалена успешно, False иначе
    """
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
        return True
    except TelegramAPIError as e:
        logger.error(f"Error removing keyboard from message {message_id}: {e}")
        return False

async def edit_message_with_reaction(bot: Bot, chat_id: int, message_id: int, joke_text: str, reaction: str, reply_markup: InlineKeyboardMarkup = None) -> bool:
    """
    Редактирует сообщение, добавляя пометку о реакции пользователя
    
    Args:
        bot (Bot): Объект бота
        chat_id (int): ID чата
        message_id (int): ID сообщения
        joke_text (str): Текст анекдота
        reaction (str): Реакция пользователя ('like', 'dislike' или 'none')
        reply_markup (InlineKeyboardMarkup, optional): Новая клавиатура
        
    Returns:
        bool: True если сообщение было отредактировано успешно, False иначе
    """
    try:
        # Определяем эмоджи и текст для реакции
        if reaction == 'like':
            reaction_emoji = "👍"
        elif reaction == 'dislike':
            reaction_emoji = "👎"
        else:
            reaction_emoji = ""
        
        # Формируем новый текст сообщения
        if reaction_emoji:
            formatted_message = f"{joke_text}\n\n{reaction_emoji}"
        else:
            formatted_message = joke_text
        
        # Обновляем текст сообщения
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=formatted_message
        )
        
        # Если передан reply_markup, обновляем клавиатуру
        if reply_markup is not None:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            )
        
        return True
    except TelegramAPIError as e:
        logger.error(f"Error editing message {message_id} with reaction: {e}")
        return False

async def create_dynamic_keyboard(
    users_jokes_id: int | None,
    message_id: int,
    current_state: str = "full" # "full", "reaction_only", "nav_only", "none"
) -> InlineKeyboardMarkup:
    """
    Создает динамическую клавиатуру в зависимости от текущего состояния кнопок.
    
    Args:
        users_jokes_id (int | None): ID записи в users_jokes. Может быть None, если нет активной шутки.
        message_id (int): ID сообщения.
        current_state (str): Текущее состояние клавиатуры ("full", "reaction_only", "nav_only", "none").
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с оставшимися кнопками.
    """
    logger.info(f"Creating dynamic keyboard: users_jokes_id={users_jokes_id}, message_id={message_id}, current_state={current_state}")
    
    keyboard_rows = []
    
    # Кнопки реакции, только если есть users_jokes_id и они должны быть в текущем состоянии
    if users_jokes_id is not None and current_state in ["full", "reaction_only"]:
        reaction_suffix = "reaction_full" if current_state == "full" else "reaction_only"
        like_callback = f"like_{users_jokes_id}_{message_id}_{reaction_suffix}"
        dislike_callback = f"dislike_{users_jokes_id}_{message_id}_{reaction_suffix}"
        keyboard_rows.append([
            InlineKeyboardButton(
                text="👍",
                callback_data=like_callback
            ),
            InlineKeyboardButton(
                text="👎",
                callback_data=dislike_callback
            )
        ])
        logger.info(f"Added reaction buttons with suffix: {reaction_suffix}")
        logger.info(f"Like callback_data: {like_callback}")
        logger.info(f"Dislike callback_data: {dislike_callback}")
    
    # Кнопки навигации, если они должны быть в текущем состоянии и есть users_jokes_id
    if current_state in ["full", "nav_only"]:
        nav_suffix = "nav_full" if current_state == "full" else "nav_only"
        change_topic_callback = f"change_topic_{users_jokes_id}_{message_id}_{nav_suffix}"
        next_joke_callback = f"next_joke_{users_jokes_id}_{message_id}_{nav_suffix}"
        keyboard_rows.append([ 
            InlineKeyboardButton(
                text="🔄 Сменить тему",
                callback_data=change_topic_callback
            ),
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=next_joke_callback
            )
        ]) 
        logger.info(f"Added navigation buttons with suffix: {nav_suffix}")
        logger.info(f"Change topic callback_data: {change_topic_callback}")
        logger.info(f"Next joke callback_data: {next_joke_callback}")
    
    logger.info(f"Created keyboard with {len(keyboard_rows)} rows")
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
