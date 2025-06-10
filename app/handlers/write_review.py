from aiogram import Router, F, Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from app.states.state_config import get_state_config, ReviewStates
from app.services.database import DBService
from app.config.logging import app_logger
from app.utils.message_utils import remove_keyboard_from_context
from app.utils.message_utils import send_supplier_card
from app.handlers.my_requests import create_supplier_response_keyboard

router = Router(name="write_review")

@router.callback_query(F.data.startswith("write_review:"))
async def start_write_review(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Remove keyboard from previous supplier card
    await remove_keyboard_from_context(callback.bot, callback)
    supplier_id = int(callback.data.split(":")[1])
    await state.update_data(review_supplier_id=supplier_id)
    config = get_state_config(ReviewStates.waiting_mark)
    await state.set_state(ReviewStates.waiting_mark)
    await callback.message.answer(config["text"], reply_markup=config["markup"])

@router.callback_query(ReviewStates.waiting_mark, F.data.startswith("review_mark:"))
async def review_choose_mark(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Remove keyboard from previous review step
    await remove_keyboard_from_context(callback.bot, callback)
    mark = int(callback.data.split(":")[1])
    await state.update_data(review_mark=mark)
    config = get_state_config(ReviewStates.waiting_text)
    await state.set_state(ReviewStates.waiting_text)
    await callback.message.answer(config["text"], reply_markup=config["markup"])
    

@router.message(ReviewStates.waiting_text)
async def review_write_text(message: Message, state: FSMContext):
    # Remove keyboard from previous review step
    await remove_keyboard_from_context(message.bot, message)
    text = message.text.strip()
    await state.update_data(review_text=text)
    # Показываем подтверждение
    data = await state.get_data()
    mark = data.get("review_mark")
    confirm_text = f"Ваша оценка: {mark}\nВаш отзыв:\n{text}\n\nВсе верно?"
    config = get_state_config(ReviewStates.confirm)
    await state.set_state(ReviewStates.confirm)
    await message.answer(confirm_text, reply_markup=config["markup"])

@router.callback_query(ReviewStates.confirm, F.data == "review_send")
async def review_send(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Remove keyboard from previous review step
    await remove_keyboard_from_context(callback.bot, callback)
    data = await state.get_data()
    print(data)
    supplier_id = data.get("review_supplier_id")
    mark = data.get("review_mark")
    text = data.get("review_text")
    author_id = data.get("request_id")
    # Save review
    success = await DBService.add_review(author_id, supplier_id, mark, text)
    if success:
        await callback.message.answer("Спасибо! Ваш отзыв успешно добавлен.")
        # Show supplier card again
        suppliers = data.get("request_suppliers", [])
        request_id = data.get("request_id")
        # Find supplier dict by id
        supplier = next((s for s in suppliers if s.get("id") == supplier_id), None)
        if supplier:
            # Get current index for navigation
            current_index = suppliers.index(supplier)
            keyboard = create_supplier_response_keyboard(supplier, current_index, len(suppliers), request_id, can_write_review=True)
            await send_supplier_card(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                supplier=supplier,
                keyboard=keyboard
            )
    else:
        await callback.message.answer("Произошла ошибка при сохранении отзыва. Попробуйте позже.")
    await state.clear() 

@router.callback_query(ReviewStates.waiting_mark, F.data == "back_to_viewing_request_suppliers")
async def back_to_viewing_request_suppliers(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Handler for 'Back to supplier' button: just deletes the review message, returning user to supplier card.
    """
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        app_logger.error(f"Failed to delete review message: {e}")

def register_handlers(dp):
    """Register all handlers from this module"""
    dp.include_router(router) 