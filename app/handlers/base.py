from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional
import logging

from app.utils.message_utils import remove_keyboard_from_context, edit_message_text_and_keyboard
from app.states.state_config import get_state_config, get_previous_state

# Создаем роутер для базовых команд
router = Router()

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
    Доступные команды:
    /start - Начать работу с ботом
    /help - Показать справку
    """
    await message.answer(help_text)


@router.callback_query(F.data.startswith("back_to_state:"))
async def handle_back_to_state(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки возврата к конкретному состоянию
    Формат callback_data: back_to_state:{group_name}:{state_name}
    Например: back_to_state:RegistrationStates:waiting_email
    """
    await callback.answer()
    
    try:
        # Получаем данные из callback_data
        callback_parts = callback.data.split(':')
        if len(callback_parts) != 3:
            await callback.message.answer("Неверный формат данных для возврата к состоянию")
            return
            
        group_name = callback_parts[1]
        state_name = callback_parts[2]
        
        # Импортируем группы состояний
        from app.states.states import RegistrationStates, SupplierCreationStates
        from aiogram.fsm.state import State
        
        # Определяем группу состояний на основе group_name
        state_group = None
        if group_name == "RegistrationStates":
            state_group = RegistrationStates
        elif group_name == "SupplierCreationStates":
            state_group = SupplierCreationStates
        else:
            await callback.message.answer(f"Неизвестная группа состояний: {group_name}")
            return
            
        # Получаем состояние из указанной группы
        target_state = getattr(state_group, state_name, None)
        
        if isinstance(target_state, State):
            # Получаем конфигурацию для целевого состояния
            state_config = get_state_config(target_state)
            
            if state_config:
                # Получаем текст сообщения
                message_text = ""
                
                # Проверяем наличие функции формирования текста или статического текста
                if "text_func" in state_config:
                    # Для состояний с категориями и подкатегориями
                    if target_state == SupplierCreationStates.waiting_main_category:
                        message_text = await state_config["text_func"](state)
                    elif target_state == SupplierCreationStates.waiting_subcategory:
                        # Получаем выбранную категорию из состояния
                        state_data = await state.get_data()
                        selected_category = state_data.get("main_category", "")
                        if selected_category:
                            message_text, _ = await state_config["text_func"](selected_category, state)
                        else:
                            # Если категория не выбрана, возвращаемся к выбору категории
                            await callback.message.answer("Произошла ошибка. Пожалуйста, выберите категорию заново.")
                            await state.set_state(SupplierCreationStates.waiting_main_category)
                            return
                else:
                    # Для состояний со статическим текстом
                    message_text = state_config.get("text", "Возврат к предыдущему шагу")
                
                # Устанавливаем целевое состояние
                await state.set_state(target_state)
                
                # Редактируем текущее сообщение вместо отправки нового
                result = await edit_message_text_and_keyboard(
                    bot=bot,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=message_text,
                    reply_markup=state_config.get("markup")
                )
                
                # Если редактирование не удалось, отправляем новое сообщение
                if not result:
                    await callback.message.answer(
                        message_text,
                        reply_markup=state_config.get("markup")
                    )
            else:
                await callback.message.answer("Конфигурация для указанного состояния не найдена")
        else:
            await callback.message.answer(f"Состояние {state_name} не найдено в группе {group_name}")
    except Exception as e:
        logging.error(f"Ошибка при возврате к состоянию: {e}")
        await callback.message.answer("Ошибка при возврате к предыдущему шагу")

def register_handlers(dp):
    dp.include_router(router)