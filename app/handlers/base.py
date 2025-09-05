from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import text
import logging
import asyncio

from app.states.states import JokeStates
from app.services.deepseek import DeepSeekService
from app.services.database import DBService, get_db_session
from app.utils.message_utils import send_joke_message

logger = logging.getLogger(__name__)

router = Router(name="base_commands")

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    # Приветственное сообщение
    welcome_text = (
        " Добро пожаловать в бот анекдотов!\n\n"
        "Я помогу вам найти смешные анекдоты на любую тему. "
        "Просто напишите, о чем хотите посмеяться, и я найду для вас подходящий анекдот!"
    )
    await message.answer(welcome_text)
    # Добавляем пользователя в БД (если его нет)
    from sqlalchemy import text
    async with get_db_session() as session:
        await session.execute(
            text("INSERT INTO users (tg_id) VALUES (:tg_id) ON CONFLICT (tg_id) DO NOTHING"),
            {"tg_id": message.from_user.id}
        )
        await session.commit()
    # Вызываем функцию для запроса темы
    await request_joke_topic(message, state)

async def request_joke_topic(message: types.Message, state: FSMContext):
    """
    Функция для запроса темы анекдота с inline кнопкой
    """
    request_text = (
        " Введите тему для анекдота в произвольной форме:\n\n"
        "Например: 'про программистов', 'про кошек', 'про работу' и т.д."
    )
    
    # Создаем inline клавиатуру с кнопкой "случайный"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Случайный анекдот",
                    callback_data=f"random_joke_{message.from_user.id}"
                )
            ]
        ]
    )
    
    await message.answer(request_text, reply_markup=keyboard)
    
    # Устанавливаем состояние ожидания темы
    await state.set_state(JokeStates.waiting_topic)

@router.message(JokeStates.waiting_topic)
async def process_topic(message: types.Message, state: FSMContext):
    """Обработка введенной пользователем темы"""
    import random
    topic = message.text.strip()
    user_id = message.from_user.id
    
    if not topic:
        await message.answer("Пожалуйста, введите тему для анекдота.")
        return
    
    await message.answer("🤔 Генерирую анекдоты... Это может занять несколько секунд.")
    
    try:
        deepseek_service = DeepSeekService.get_instance()
        jokes_response = await deepseek_service.request_jokes(topic, n=5)
        jokes = await deepseek_service.parse_with_retry(
            content=jokes_response,
            parse_func=DeepSeekService._parse_jokes_list
        )
        idx = random.randint(0, len(jokes) - 1)
        joke_text = jokes[idx]["text"]
        # Сохраняем все анекдоты в БД, users_jokes только для выбранного
        topic_id, joke_ids, users_jokes_id = await deepseek_service.save_jokes_to_db(topic, jokes, user_id, idx)
        
        # Проверяем, что users_jokes_id получен корректно
        if users_jokes_id is not None:
            await send_joke_message(message, joke_text, users_jokes_id)
        else:
            logger.error(f"Failed to get users_jokes_id for user {user_id}, topic '{topic}'")
            await message.answer("😔 Извините, произошла ошибка при сохранении анекдота. Попробуйте еще раз.")
    except Exception as e:
        logger.error(f"Error processing topic '{topic}' for user {user_id}: {str(e)}")
        await message.answer(
            "😔 Извините, произошла ошибка при генерации анекдота. "
            "Попробуйте еще раз или выберите другую тему."
        )
    
    await state.clear()

async def request_joke_with_retry(deepseek_service: DeepSeekService, topic: str, max_retries: int = 3) -> str:
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempting to request joke for topic '{topic}', attempt {attempt + 1}/{max_retries}")
            return await deepseek_service.request_joke(topic)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for topic '{topic}': {str(e)}")
            if attempt == max_retries - 1:
                # Последняя попытка - пробрасываем ошибку
                raise
            else:
                # Ждем перед следующей попыткой
                wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 секунды
                logger.debug(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)

@router.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_reaction_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    logger.debug(f"Received callback_data in handle_reaction_callback: {callback.data}")
    try:
        # Парсим callback_data: "like_123_456_reaction_full" или "dislike_123_456_reaction_only"
        parts = callback.data.split("_")
        
        reaction_type = parts[0] # like или dislike
            
        users_jokes_id = int(parts[1])
        message_id = int(parts[2])

        # Суффикс может быть "reaction_full" или "reaction_only"
        if len(parts) >= 5:
            current_suffix = f"{parts[3]}_{parts[4]}" # reaction_full или reaction_only
        else:
            current_suffix = parts[3] # reaction_full или reaction_only
        
        logger.debug(f"Processing {reaction_type} for users_jokes_id={users_jokes_id}, message_id={message_id}, user_id={user_id}, suffix={current_suffix}")
        
        # Обновляем запись в БД по users_jokes.id
        await DBService.update_users_jokes_reaction_by_id(users_jokes_id, reaction_type)
        
        # Получаем текст анекдота и тему для редактирования сообщения
        joke_text = await DBService.get_joke_text_by_users_jokes_id(users_jokes_id, user_id)
        if not joke_text:
            await callback.answer("Анекдот не найден")
            return
        
        # Определяем новое состояние клавиатуры
        new_state = "nav_only" if current_suffix == "reaction_full" else "none"
        
        # Создаем новую клавиатуру без кнопок реакции
        from app.utils.message_utils import create_dynamic_keyboard, edit_message_with_reaction

        new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
        
        # Редактируем сообщение, обновляя текст и клавиатуру
        message_edited = await edit_message_with_reaction(
            callback.bot, 
            chat_id, 
            message_id, 
            joke_text, 
            reaction_type, # Передаем тип реакции для эмоджи
            reply_markup=new_keyboard
        )
        if not message_edited:
            logger.error(f"Failed to edit message {message_id} with new joke")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling reaction callback for user {user_id} with data {callback.data}: {str(e)}")
        await callback.answer(f"Произошла ошибка при обработке реакции (данные: {callback.data})", show_alert=True)

@router.callback_query(F.data.startswith("random_joke_"))
async def handle_random_joke_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    logger.debug(f"Received callback_data in handle_random_joke_callback: {callback.data}")
    try:
        # Получаем случайный анекдот, который пользователь ещё не видел
        joke_row = await DBService.get_random_unseen_joke_for_user(user_id)
        if not joke_row:
            await callback.answer("Нет новых анекдотов для вас! Попробуйте позже.", show_alert=True)
            return

        try:
            joke_id = joke_row["id"]
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to get joke_id from joke_row: {e}, joke_row: {joke_row}")
            await callback.answer("Ошибка при получении анекдота")
            return
            
        # Дополнительная проверка joke_id
        if not isinstance(joke_id, int) or joke_id <= 0:
            logger.error(f"Invalid joke_id type or value: {type(joke_id)}, value: {joke_id}")
            await callback.answer("Ошибка при получении анекдота")
            return
            
        joke_text = joke_row["joke"]

        # Создаём запись в users_jokes (реакция по умолчанию 'skip') и сразу получаем id
        users_jokes_id = await DBService.record_user_joke_interaction(user_id, joke_id, reaction="skip")

        # Отправляем анекдот с кнопками (состояние "full")
        from app.utils.message_utils import send_joke_message
        if users_jokes_id is not None:
            await send_joke_message(callback.message, joke_text, users_jokes_id)
        else:
            await send_joke_message(callback.message, joke_text, None)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error handling random joke callback for user {user_id} with data {callback.data}: {str(e)}")
        await callback.answer(f"Произошла ошибка при получении анекдота (данные: {callback.data})", show_alert=True)

@router.callback_query(F.data.startswith("change_topic_"))
async def handle_change_topic_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    logger.debug(f"Received callback_data in handle_change_topic_callback: {callback.data}")
    try:
        # Парсим callback_data: "change_topic_456_nav_full" или "change_topic_456_nav_only"
        parts = callback.data.split("_")
        message_id = int(parts[3])
        users_jokes_id = int(parts[2])
        current_suffix = parts[4] + "_" + parts[5] # nav_full или nav_only
        
        # Определяем новое состояние клавиатуры
        new_state = "reaction_only" if current_suffix == "nav_full" else "none"
        
        # Создаем новую клавиатуру без кнопок навигации
        from app.utils.message_utils import create_dynamic_keyboard
        if users_jokes_id is not None:  # Только если есть users_jokes_id для создания кнопок реакции
            new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
            await callback.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=new_keyboard
                    )
        else:  # Если users_jokes_id нет, удаляем всю клавиатуру
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None
            )
            
        await callback.answer()
        await request_joke_topic(callback.message, state)
        
    except Exception as e:
        logger.error(f"Error handling change topic callback for user {user_id} with data {callback.data}: {str(e)}")
        await callback.answer(f"Произошла ошибка при обработке запроса (данные: {callback.data})", show_alert=True)

@router.callback_query(F.data.startswith("next_joke_"))
async def handle_next_joke_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    logger.debug(f"Received callback_data in handle_next_joke_callback: {callback.data}")
    try:
        # Парсим callback_data: "next_joke_456_nav_full" или "next_joke_456_nav_only"
        parts = callback.data.split("_")
        if len(parts) < 5: # Минимум 5 частей: next, joke, message_id, nav, suffix
            await callback.answer("Ошибка в данных кнопки")
            return
        
        
        message_id = int(parts[3])  # parts[2] содержит message_id, так как next_joke разбивается на две части
        users_jokes_id = int(parts[2])
        current_suffix = parts[4] + "_" + parts[5] # nav_full или nav_only

        # Определяем новое состояние клавиатуры
        new_state = "reaction_only" if current_suffix == "nav_full" else "none"
        
        # Создаем новую клавиатуру без кнопок навигации
        from app.utils.message_utils import create_dynamic_keyboard
        if users_jokes_id is not None:  # Только если есть users_jokes_id для создания кнопок реакции
            new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=new_keyboard
            )
        else:  # Если users_jokes_id нет, удаляем всю клавиатуру
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None
            )
            
        # Получаем случайный анекдот, который пользователь ещё не видел
        joke_row = await DBService.get_random_joke_for_user(user_id)
        if not joke_row:
            await callback.answer("Нет новых анекдотов для вас! Попробуйте позже.", show_alert=True)
            return
        
        try:
            joke_id = joke_row["id"]
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to get joke_id from joke_row: {e}, joke_row: {joke_row}")
            await callback.answer("Ошибка при получении анекдота")
            return
            
        joke_text = joke_row["joke"]
        
        # Создаём запись в users_jokes (реакция по умолчанию 'skip') и сразу получаем id
        users_jokes_id_new = await DBService.record_user_joke_interaction(user_id, joke_id, reaction="skip")
            
        # Отправляем новый анекдот в ТО ЖЕ сообщение, меняя текст и сохраняя клавиатуру
        from app.utils.message_utils import send_joke_message

        # Вместо редактирования старого сообщения, отправляем новое
        await send_joke_message(callback.message, joke_text, users_jokes_id_new)
        

        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling next joke callback for user {user_id} with data {callback.data}: {str(e)}")
        await callback.answer(f"Произошла ошибка при получении анекдота (данные: {callback.data})", show_alert=True)



def register_handlers(dp):
    dp.include_router(router)