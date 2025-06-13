from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext, StorageKey
from aiogram.fsm.state import State
from app.states.states import HelpStates
from app.services import get_db_session, DBService, admin_chat_service
from app.keyboards.inline import get_main_menu_keyboard_by_role
import logging

router = Router()
logger = logging.getLogger(__name__)

# 1. Обработчик кнопки "Помощь"
@router.callback_query(F.data == "help_action")
async def help_action_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(HelpStates.waiting_problem_description)
    await callback.message.answer("Пожалуйста, опишите вашу проблему или вопрос. Чем подробнее, тем быстрее мы сможем помочь.")

# 2. Обработка ввода описания проблемы
@router.message(HelpStates.waiting_problem_description)
async def process_problem_description(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or "-"
    problem_text = message.text.strip()

    # Сохраняем в БД
    async with get_db_session() as session:
        db_service = DBService(session)
        query = """
            INSERT INTO help_requests (user_id, request, status, created_at)
            VALUES (:user_id, :request, 'pending', NOW())
            RETURNING id
        """
        result = await db_service.execute_query(query, {"user_id": user_id, "request": problem_text})
        help_request_id = result.scalar_one()
        await db_service.commit()

    await state.clear()
    # Получаем роль пользователя для главного меню
    async with get_db_session() as session:
        db_service = DBService(session)
        user_data = await db_service.get_user_by_id(user_id)
        user_role = user_data["role"] if user_data and "role" in user_data else None
    await message.answer(
        "Спасибо! Ваш вопрос отправлен администраторам. Мы ответим вам в ближайшее время.",
        reply_markup=get_main_menu_keyboard_by_role(user_role)
    )

    # Отправляем в чат админов с кнопкой "Забрать себе"
    admin_text = f"🆘 <b>Новый вопрос от пользователя</b>\n\n" \
                 f"<b>ID:</b> <code>{user_id}</code>\n" \
                 f"<b>Username:</b> {username}\n" \
                 f"<b>Вопрос:</b> {problem_text}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Забрать себе",
                    callback_data=admin_chat_service.create_admin_callback_data(
                        "take_help_request", help_request_id=help_request_id, user_id=user_id
                    )
                )
            ]
        ]
    )
    await admin_chat_service.send_message(bot, admin_text, reply_markup=keyboard)

# 3. Обработчик кнопки "Забрать себе" для админа
@router.callback_query(F.data.startswith("admin:take_help_request"))
async def admin_take_help_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    help_request_id = data.get("help_request_id")
    user_id = data.get("user_id")
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username or f"ID:{admin_id}"

    if not help_request_id:
        await callback.message.answer("Ошибка: не найден ID запроса.")
        return

    # Редактируем сообщение в чате админов
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n🔄 Вопрос взят на обработку администратором @{admin_username}",
            reply_markup=None
        )
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        await callback.message.answer(f"Вопрос взят на обработку администратором @{admin_username}")

    # Получаем текст вопроса из БД и отправляем админу в личку с кнопкой
    try:
        async with get_db_session() as session:
            db_service = DBService(session)
            query = "SELECT request FROM help_requests WHERE id = :id"
            result = await db_service.execute_query(query, {"id": int(help_request_id)})
            row = result.mappings().first()
            question_text = row["request"] if row else "(вопрос не найден)"
        # Кнопка для ввода ответа
        answer_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Ввести ответ",
                    callback_data=f"admin:answer_help_request:{help_request_id}:{user_id}"
                )]
            ]
        )
        await bot.send_message(
            chat_id=admin_id,
            text=f"🆘 Вопрос пользователя:\n\n{question_text}",
            reply_markup=answer_keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке вопроса админу в личку: {e}")
        await callback.message.answer("Ошибка при отправке вопроса в личку. Введите ответ здесь.")

# Новый обработчик для кнопки 'Ввести ответ' в личке
@router.callback_query(F.data.startswith("admin:answer_help_request"))
async def admin_start_answer_help(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Парсим параметры
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.message.answer("Ошибка: не удалось определить вопрос.")
        return
    help_request_id = parts[2]
    user_id = parts[3]
    await state.update_data(help_request_id=help_request_id, help_user_id=user_id)
    await state.set_state(HelpStates.waiting_admin_answer)
    await callback.message.answer("Пожалуйста, введите ответ пользователю:", reply_markup=ReplyKeyboardRemove())

# 4. Обработка ответа админа
@router.message(HelpStates.waiting_admin_answer)
async def process_admin_answer(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    help_request_id = data.get("help_request_id")
    user_id = data.get("help_user_id")
    answer_text = message.text.strip()

    if not help_request_id or not user_id:
        await message.answer("Ошибка: не найден ID запроса или пользователя.")
        await state.clear()
        return

    # Получаем текст вопроса для пользователя
    async with get_db_session() as session:
        db_service = DBService(session)
        query = "SELECT request FROM help_requests WHERE id = :id"
        result = await db_service.execute_query(query, {"id": int(help_request_id)})
        row = result.mappings().first()
        question_text = row["request"] if row else "(вопрос не найден)"

    # Обновляем запись в БД
    async with get_db_session() as session:
        db_service = DBService(session)
        query = """
            UPDATE help_requests SET answer = :answer, status = 'answered', admin_id = :admin_id WHERE id = :id
        """
        await db_service.execute_query(query, {"id": int(help_request_id), "answer": answer_text, "admin_id": message.from_user.id})
        await db_service.commit()

    # Отправляем ответ пользователю с его вопросом
    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=f"💬 Ответ от администратора на ваш вопрос:\n\n<b>Ваш вопрос:</b> {question_text}\n\n<b>Ответ:</b> {answer_text}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю {user_id}: {e}")
        await message.answer(f"Ошибка при отправке ответа пользователю: {e}")

    await state.clear()
    # Получаем роль админа для главного меню
    admin_id = message.from_user.id
    async with get_db_session() as session:
        db_service = DBService(session)
        user_data = await db_service.get_user_by_id(admin_id)
        user_role = user_data["role"] if user_data and "role" in user_data else None
    await message.answer(
        "Ответ отправлен пользователю и сохранён в базе данных.",
        reply_markup=get_main_menu_keyboard_by_role(user_role)
    )

def register_handlers(dp):
    dp.include_router(router)