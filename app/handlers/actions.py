"""
Обработчики для действий без состояний.
Используется для сценариев с простой навигацией по меню.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.utils.message_utils import remove_keyboard_from_context, edit_message_text_and_keyboard
from app.config.action_config import get_action_config
from app.states.states import SupplierCreationStates
from app.states.state_config import get_state_config

# Инициализируем роутер
router = Router()

@router.callback_query(F.data.in_(["suppliers", "requests_list", "favorites_list", "help_action",
                               "my_suppliers"]))
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
    
    # Редактируем текущее сообщение вместо отправки нового
    result = await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=action_config.get("text", "Выполняется действие..."),
        reply_markup=action_config.get("markup")
    )
    
    # Если редактирование не удалось, отправляем новое сообщение
    if not result:
        await callback.message.answer(
            action_config.get("text", "Выполняется действие..."),
            reply_markup=action_config.get("markup")
        )

@router.callback_query(F.data == "create_supplier")
async def handle_create_supplier(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для начала процесса создания поставщика.
    Переводит пользователя в состояние ввода названия компании.
    """
    await callback.answer()
    
    # Получаем информацию о пользователе из БД
    from app.services import get_db_session, DBService
    
    async with get_db_session() as session:
        db_service = DBService(session)
        user_data = await db_service.get_user_by_id(callback.from_user.id)
        
    if not user_data:
        await callback.message.answer(
            "Невозможно создать поставщика. Пожалуйста, сначала пройдите регистрацию через команду /start."
        )
        return
    
    # Сохраняем информацию о пользователе в состояние
    await state.update_data(
        user_id=user_data["tg_id"],
        username=user_data["username"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        email=user_data["email"],
        phone=user_data["phone"]
    )
    
    # Получаем конфигурацию для первого состояния создания поставщика
    company_name_config = get_state_config(SupplierCreationStates.waiting_company_name)
    
    # Устанавливаем состояние ввода названия компании
    await state.set_state(SupplierCreationStates.waiting_company_name)
    
    # Редактируем текущее сообщение
    result = await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=company_name_config["text"],
        reply_markup=company_name_config.get("markup")
    )
    
    # Если редактирование не удалось, отправляем новое сообщение
    if not result:
        await callback.message.answer(
            company_name_config["text"],
            reply_markup=company_name_config.get("markup")
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