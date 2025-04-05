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
