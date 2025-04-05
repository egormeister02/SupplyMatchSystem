from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional

from app.utils.message_utils import remove_keyboard_from_context
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

@router.callback_query(F.data == "back")
async def handle_back_button(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """
    Универсальный обработчик для кнопки "Назад"
    Действует так же, как и конкретные back_to_x кнопки
    """
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Получаем текущее состояние пользователя
    current_state = await state.get_state()
    
    if not current_state:
        await callback.message.answer("Нет активного состояния")
        return
    
    # Находим предыдущее состояние из конфигурации
    from app.states.states import RegistrationStates
    
    # Преобразуем строковое представление состояния в объект State
    state_parts = current_state.split(":")
    if len(state_parts) != 2:
        await callback.message.answer("Невозможно определить текущее состояние")
        return
    
    # Получаем объект State для текущего состояния
    try:
        current_state_obj = getattr(RegistrationStates, state_parts[1])
        prev_state_obj = get_previous_state(current_state_obj)
        
        if prev_state_obj:
            # Получаем конфигурацию предыдущего состояния
            prev_config = get_state_config(prev_state_obj)
            
            if prev_config:
                # Устанавливаем предыдущее состояние
                await state.set_state(prev_state_obj)
                
                # Отправляем сообщение, связанное с предыдущим состоянием
                await callback.message.answer(
                    prev_config.get("text", "Возврат к предыдущему шагу"),
                    reply_markup=prev_config.get("markup")
                )
            else:
                await callback.message.answer("Конфигурация для предыдущего состояния не найдена")
        else:
            await callback.message.answer("Нет предыдущего шага")
    except AttributeError:
        await callback.message.answer("Невозможно определить предыдущее состояние")

@router.callback_query(F.data.startswith("back_to_"))
async def handle_back_to_state(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки возврата к конкретному состоянию
    Формат callback_data: back_to_{state_name}
    Например: back_to_waiting_email
    """
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Получаем имя состояния из callback_data
    target_state_name = callback.data.replace("back_to_", "")
    
    # Ищем нужное состояние в StateGroup
    from app.states.states import RegistrationStates
    
    # Проверяем, что состояние существует
    try:
        from aiogram.fsm.state import State
        # Получаем объект состояния
        target_state = getattr(RegistrationStates, target_state_name, None)
        
        if isinstance(target_state, State):
            # Получаем конфигурацию для целевого состояния
            state_config = get_state_config(target_state)
            
            if state_config:
                # Устанавливаем целевое состояние
                await state.set_state(target_state)
                
                # Отправляем сообщение с соответствующей клавиатурой
                await callback.message.answer(
                    state_config.get("text", "Возврат к предыдущему шагу"),
                    reply_markup=state_config.get("markup")
                )
            else:
                await callback.message.answer("Конфигурация для указанного состояния не найдена")
        else:
            await callback.message.answer("Невозможно вернуться к указанному шагу")
    except (AttributeError, ImportError):
        await callback.message.answer("Ошибка при возврате к предыдущему шагу")

def register_handlers(dp):
    dp.include_router(router)
