"""
Utility functions for message operations
"""

from typing import Union, Optional
from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError

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
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        return True
    except TelegramAPIError:
        # Message can't be edited or hasn't changed
        return False 