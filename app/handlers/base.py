from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional
import logging

from app.utils.message_utils import remove_keyboard_from_context, edit_message_text_and_keyboard, send_review_card
from app.states.state_config import get_state_config, get_previous_state
from app.states.states import RegistrationStates, SupplierCreationStates, SupplierSearchStates, RequestCreationStates, MySupplierStates, MyRequestStates, ReviewStates
from app.config.logging import app_logger
from app.services.database import DBService

# Создаем роутер для базовых команд с более низким приоритетом
router = Router(name="base_commands")

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
        from aiogram.fsm.state import State
        
        # Определяем группу состояний на основе group_name
        state_group = None
        if group_name == "RegistrationStates":
            state_group = RegistrationStates
        elif group_name == "SupplierCreationStates":
            state_group = SupplierCreationStates
        elif group_name == "SupplierSearchStates":
            state_group = SupplierSearchStates
        elif group_name == "RequestCreationStates":
            state_group = RequestCreationStates
        elif group_name == "MySupplierStates":
            state_group = MySupplierStates
        elif group_name == "MyRequestStates":
            state_group = MyRequestStates
        elif group_name == "ReviewStates":
            state_group = ReviewStates
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
                    if target_state == SupplierCreationStates.waiting_main_category or target_state == SupplierSearchStates.waiting_category:
                        message_text = await state_config["text_func"](state)
                    elif target_state == SupplierCreationStates.waiting_subcategory or target_state == SupplierSearchStates.waiting_subcategory:
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

@router.callback_query(F.data.startswith("show_reviews:"))
async def show_reviews_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки 'Посмотреть отзывы'"""
    await callback.answer()
    supplier_id = int(callback.data.split(":")[1])
    reviews = await DBService.get_reviews_for_supplier(supplier_id)
    await state.update_data(review_supplier_id=supplier_id, reviews=reviews, review_index=0, review_message_id=None)
    msg_id = await send_review_card(bot, callback.message.chat.id, reviews, 0)
    await state.update_data(review_message_id=msg_id)

@router.callback_query(F.data.startswith("review_next:"))
async def review_next_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    reviews = data.get("reviews", [])
    idx = int(callback.data.split(":")[1])
    if 0 <= idx < len(reviews):
        old_msg_id = data.get("review_message_id")
        msg_id = await send_review_card(bot, callback.message.chat.id, reviews, idx, message_id=old_msg_id)
        await state.update_data(review_index=idx, review_message_id=msg_id)

@router.callback_query(F.data.startswith("review_prev:"))
async def review_prev_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    reviews = data.get("reviews", [])
    idx = int(callback.data.split(":")[1])
    if 0 <= idx < len(reviews):
        old_msg_id = data.get("review_message_id")
        msg_id = await send_review_card(bot, callback.message.chat.id, reviews, idx, message_id=old_msg_id)
        await state.update_data(review_index=idx, review_message_id=msg_id)

@router.callback_query(F.data == "review_back")
async def review_back_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    old_msg_id = data.get("review_message_id")
    if old_msg_id:
        try:
            await bot.delete_message(callback.message.chat.id, old_msg_id)
        except Exception:
            pass
    # Никаких дополнительных действий, возврат к карточке поставщика

def register_handlers(dp):
    dp.include_router(router)