"""
Обработчики для действий без состояний.
Используется для сценариев с простой навигацией по меню.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.utils.message_utils import remove_keyboard_from_context, edit_message_text_and_keyboard
from app.config.action_config import get_action_config

# Инициализируем роутер
router = Router()

@router.callback_query(F.data.in_(["suppliers_list", "requests_list", "favorites_list", "help_action",
                               "suppliers_electronics", "suppliers_food"]))
async def handle_menu_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для пунктов меню без состояний.
    Получает текст и клавиатуру из конфигурации действий.
    """
    await callback.answer()
    
    # Получаем действие из callback_data
    action = callback.data
    
    # Получаем конфигурацию для действия
    action_config = get_action_config(action)
    
    if not action_config:
        await callback.message.answer("Неизвестное действие")
        return
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Показываем соответствующее сообщение с клавиатурой
    await callback.message.answer(
        action_config.get("text", "Выполняется действие..."),
        reply_markup=action_config.get("markup")
    )

@router.callback_query(F.data.startswith("back_to_action:"))
async def handle_back_to_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки возврата к действию.
    Формат callback_data: back_to_action:{action_name}
    Например: back_to_action:main_menu
    """
    await callback.answer()
    
    # Получаем имя действия из callback_data
    target_action = callback.data.replace("back_to_action:", "")
    
    # Получаем конфигурацию для целевого действия
    action_config = get_action_config(target_action)
    
    if not action_config:
        await callback.message.answer("Конфигурация для указанного действия не найдена")
        return
    
    # Редактируем текущее сообщение вместо отправки нового
    result = await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=action_config.get("text", "Возврат к предыдущему меню"),
        reply_markup=action_config.get("markup")
    )
    
    # Если редактирование не удалось, отправляем новое сообщение
    if not result:
        await callback.message.answer(
            action_config.get("text", "Возврат к предыдущему меню"),
            reply_markup=action_config.get("markup")
        )

# Добавление роутера в основной диспетчер
def register_handlers(dp):
    """Register action handlers"""
    dp.include_router(router) 