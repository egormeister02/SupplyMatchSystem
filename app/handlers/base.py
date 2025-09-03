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
            logger.info(f"Attempting to request joke for topic '{topic}', attempt {attempt + 1}/{max_retries}")
            return await deepseek_service.request_joke(topic)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for topic '{topic}': {str(e)}")
            if attempt == max_retries - 1:
                # Последняя попытка - пробрасываем ошибку
                raise
            else:
                # Ждем перед следующей попыткой
                wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 секунды
                logger.info(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)

@router.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_reaction_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    logger.debug(f"Received callback_data in handle_reaction_callback: {callback.data}")
    try:
        # Парсим callback_data: "like_123_456_reaction_full" или "dislike_123_456_reaction_only"
        parts = callback.data.split("_")
        if len(parts) < 4: # Минимум 4 части: type, users_jokes_id, message_id, suffix
            await callback.answer("Ошибка в данных кнопки")
            return
        
        reaction_type = parts[0] # like или dislike
        
        try:
            users_jokes_id = int(parts[1])
        except ValueError as e:
            logger.error(f"Failed to parse users_jokes_id from parts[1]='{parts[1]}': {e}")
            await callback.answer("Ошибка в данных кнопки")
            return
            
        try:
            message_id = int(parts[2])
        except ValueError as e:
            logger.error(f"Failed to parse message_id from parts[2]='{parts[2]}': {e}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Дополнительная проверка users_jokes_id
        if users_jokes_id <= 0:
            logger.error(f"Invalid users_jokes_id: {users_jokes_id}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Суффикс может быть "reaction_full" или "reaction_only"
        if len(parts) >= 5:
            current_suffix = f"{parts[3]}_{parts[4]}" # reaction_full или reaction_only
        else:
            current_suffix = parts[3] # reaction_full или reaction_only
        
        logger.info(f"Processing {reaction_type} for users_jokes_id={users_jokes_id}, message_id={message_id}, user_id={user_id}, suffix={current_suffix}")
        
        # Обновляем запись в БД по users_jokes.id
        async with get_db_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE users_jokes 
                    SET reaction = :reaction 
                    WHERE id = :users_jokes_id
                    """
                ),
                {"reaction": reaction_type, "users_jokes_id": users_jokes_id}
            )
            await session.commit()
        
        logger.info(f"Updated reaction in database for user {user_id}, users_jokes_id {users_jokes_id}")
        
        # Получаем текст анекдота и тему для редактирования сообщения
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT j.joke, t.topic 
                    FROM users_jokes uj
                    JOIN jokes j ON j.id = uj.joke_id 
                    JOIN topics t ON t.id = j.topic_id 
                    WHERE uj.id = :users_jokes_id AND uj.user_id = :user_id
                    """
                ),
                {"users_jokes_id": users_jokes_id, "user_id": user_id}
            )
            row = result.mappings().first()
            if not row:
                await callback.answer("Анекдот не найден")
                return
            
            joke_text = row["joke"]
            topic = row["topic"]
        
        logger.info(f"Retrieved joke data: topic='{topic}', joke_text='{joke_text[:50]}...'")
        
        # Определяем новое состояние клавиатуры
        new_state = "nav_only" if current_suffix == "reaction_full" else "none"
        
        # Создаем новую клавиатуру без кнопок реакции
        from app.utils.message_utils import create_dynamic_keyboard, edit_message_with_reaction
        if users_jokes_id is not None:
            new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
        else:
            new_keyboard = await create_dynamic_keyboard(None, message_id, new_state)
        
        # Редактируем сообщение, обновляя текст и клавиатуру
        message_edited = await edit_message_with_reaction(
            callback.bot, 
            chat_id, 
            message_id, 
            joke_text, 
            topic, 
            reaction_type, # Передаем тип реакции для эмоджи
            reply_markup=new_keyboard
        )
        if not message_edited:
            logger.error(f"Failed to edit message {message_id} with new joke")
        logger.info(f"Message editing result: {message_edited}")
        
        # Дополнительно проверяем, что клавиатура действительно изменилась
        current_keyboard = callback.message.reply_markup
        if current_keyboard is None or str(current_keyboard) != str(new_keyboard):
            try:
                await callback.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=new_keyboard
                )
                logger.info(f"Successfully updated keyboard for message {message_id} to {new_state}")
            except Exception as e:
                logger.warning(f"Failed to update keyboard for message {message_id}: {e}")
        else:
            logger.info(f"Keyboard for message {message_id} already has {new_state} state, skipping update")
        
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
            
            # Если нет новых анекдотов, удаляем все кнопки
            await callback.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
            return

        # Детальное логирование joke_row для отладки
        logger.info(f"Retrieved joke_row in random_joke: {joke_row}")

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
        topic = joke_row["topic"]

        logger.info(f"Extracted joke data in random_joke: joke_id={joke_id}, topic='{topic}', joke_text='{joke_text[:50]}...'")

        # Создаём запись в users_jokes (реакция по умолчанию 'skip')
        await DBService.record_user_joke_interaction(user_id, joke_id, reaction="skip")

        # Получаем только что созданную users_jokes.id
        from sqlalchemy import text
        async with get_db_session() as session:
            res = await session.execute(
                text("SELECT id FROM users_jokes WHERE user_id = :user_id AND joke_id = :joke_id"),
                {"user_id": user_id, "joke_id": joke_id}
            )
            row = res.first()
            users_jokes_id = row[0] if row else None

        logger.info(f"Created users_jokes record in random_joke with id: {users_jokes_id}")

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
        if len(parts) < 5: # Минимум 5 частей: change, topic, message_id, nav, suffix
            await callback.answer("Ошибка в данных кнопки")
            return
        
        try:
            message_id = int(parts[2])  # parts[2] содержит message_id, так как change_topic разбивается на две части
        except ValueError as e:
            logger.error(f"Failed to parse message_id from parts[2]='{parts[2]}': {e}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Дополнительная проверка message_id
        if message_id <= 0:
            logger.error(f"Invalid message_id: {message_id}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Суффикс может быть "nav_full" или "nav_only"
        if len(parts) >= 5:
            current_suffix = f"{parts[3]}_{parts[4]}" # nav_full или nav_only
        else:
            current_suffix = parts[3] # nav_full или nav_only
        
        logger.info(f"Parsed change_topic: message_id={message_id}, current_suffix={current_suffix}")
        
        # Определяем users_jokes_id из текущей клавиатуры (если кнопки реакции еще есть)
        users_jokes_id = None
        if callback.message.reply_markup:
            for row in callback.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data and (btn.callback_data.startswith("like_") or btn.callback_data.startswith("dislike_")):
                        try:
                            users_jokes_id = int(btn.callback_data.split("_")[1])
                            break
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse users_jokes_id from {btn.callback_data}: {e}")
                            continue
                if users_jokes_id:
                    break
        
        # Дополнительная проверка users_jokes_id
        if users_jokes_id is not None and users_jokes_id <= 0:
            logger.error(f"Invalid users_jokes_id: {users_jokes_id}")
            users_jokes_id = None
        
        logger.info(f"Extracted users_jokes_id from keyboard: {users_jokes_id}")
        
        # Определяем новое состояние клавиатуры
        new_state = "reaction_only" if current_suffix == "nav_full" and users_jokes_id is not None else "none"
        
        # Создаем новую клавиатуру без кнопок навигации
        from app.utils.message_utils import create_dynamic_keyboard
        if users_jokes_id is not None: # Только если есть users_jokes_id для создания кнопок реакции
            new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
            
            # Проверяем, изменилась ли клавиатура
            current_keyboard = callback.message.reply_markup
            if current_keyboard is None or str(current_keyboard) != str(new_keyboard):
                try:
                    await callback.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=new_keyboard
                    )
                    logger.info(f"Successfully updated keyboard for message {message_id} to {new_state}")
                except Exception as e:
                    logger.warning(f"Failed to update keyboard for message {message_id}: {e}")
            else:
                logger.info(f"Keyboard for message {message_id} already has {new_state} state, skipping update")
        else: # Если users_jokes_id нет, удаляем всю клавиатуру
            current_keyboard = callback.message.reply_markup
            if current_keyboard is not None:
                try:
                    await callback.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=None
                    )
                    logger.info(f"Successfully removed keyboard for message {message_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove keyboard for message {message_id}: {e}")
            else:
                logger.info(f"Message {message_id} already has no keyboard, skipping update")
            
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
        
        try:
            message_id = int(parts[2])  # parts[2] содержит message_id, так как next_joke разбивается на две части
        except ValueError as e:
            logger.error(f"Failed to parse message_id from parts[2]='{parts[2]}': {e}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Дополнительная проверка message_id
        if message_id <= 0:
            logger.error(f"Invalid message_id: {message_id}")
            await callback.answer("Ошибка в данных кнопки")
            return
        
        # Суффикс может быть "nav_full" или "nav_only"
        if len(parts) >= 5:
            current_suffix = f"{parts[3]}_{parts[4]}" # nav_full или nav_only
        else:
            current_suffix = parts[3] # nav_full или nav_only
        
        logger.info(f"Parsed next_joke: message_id={message_id}, current_suffix={current_suffix}")
        
        # Определяем users_jokes_id из текущей клавиатуры (если кнопки реакции еще есть)
        users_jokes_id = None
        if callback.message.reply_markup:
            for row in callback.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data and (btn.callback_data.startswith("like_") or btn.callback_data.startswith("dislike_")):
                        try:
                            users_jokes_id = int(btn.callback_data.split("_")[1])
                            break
                        except (ValueError, IndexError) as e:
                            logger.error(f"Failed to parse users_jokes_id from {btn.callback_data}: {e}")
                            continue
                if users_jokes_id:
                    break
        
        # Дополнительная проверка users_jokes_id
        if users_jokes_id is not None and users_jokes_id <= 0:
            logger.error(f"Invalid users_jokes_id: {users_jokes_id}")
            users_jokes_id = None
        
        logger.info(f"Extracted users_jokes_id from keyboard: {users_jokes_id}")
        
        # Определяем новое состояние клавиатуры
        new_state = "reaction_only" if current_suffix == "nav_full" and users_jokes_id is not None else "none"
        
        # Создаем новую клавиатуру без кнопок навигации
        from app.utils.message_utils import create_dynamic_keyboard
        if users_jokes_id is not None: # Только если есть users_jokes_id для создания кнопок реакции
            new_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, new_state)
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=new_keyboard
            )
        else: # Если users_jokes_id нет, удаляем всю клавиатуру
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None
            )
            
        # Получаем случайный анекдот, который пользователь ещё не видел
        joke_row = await DBService.get_random_unseen_joke_for_user(user_id)
        if not joke_row:
            await callback.answer("Нет новых анекдотов для вас! Попробуйте позже.", show_alert=True)
            return
        
        # Детальное логирование joke_row для отладки
        logger.info(f"Retrieved joke_row: {joke_row}")
        
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
        topic = joke_row["topic"]  # Теперь это поле есть в get_random_unseen_joke_for_user
        
        logger.info(f"Extracted joke data: joke_id={joke_id}, topic='{topic}', joke_text='{joke_text[:50]}...'")
        
        # Создаём запись в users_jokes (реакция по умолчанию 'skip')
        await DBService.record_user_joke_interaction(user_id, joke_id, reaction="skip")
        
        # Получаем только что созданную users_jokes.id
        from sqlalchemy import text
        async with get_db_session() as session:
            res = await session.execute(
                text("SELECT id FROM users_jokes WHERE user_id = :user_id AND joke_id = :joke_id"),
                {"user_id": user_id, "joke_id": joke_id}
            )
            row = res.first()
            try:
                users_jokes_id_new = row[0] if row else None
            except (IndexError, TypeError) as e:
                logger.error(f"Failed to get users_jokes_id_new from row: {e}, row: {row}")
                users_jokes_id_new = None
            
        logger.info(f"Created users_jokes record with id: {users_jokes_id_new}")
        
        # Отправляем новый анекдот в ТО ЖЕ сообщение, меняя текст и сохраняя клавиатуру
        from app.utils.message_utils import edit_message_with_reaction, send_joke_message
        if users_jokes_id_new is not None:
            new_keyboard = await create_dynamic_keyboard(users_jokes_id_new, message_id, "full")
        else:
            new_keyboard = await create_dynamic_keyboard(None, message_id, "full")
        
        # Вместо редактирования старого сообщения, отправляем новое
        await send_joke_message(callback.message, joke_text, users_jokes_id_new)
        
        # Удаляем кнопки навигации у старого сообщения (оставляем только кнопки реакции)
        if users_jokes_id is not None:
            # Создаем клавиатуру только с кнопками реакции
            reaction_only_keyboard = await create_dynamic_keyboard(users_jokes_id, message_id, "reaction_only")
            
            # Проверяем, изменилась ли клавиатура
            current_keyboard = callback.message.reply_markup
            if current_keyboard is None or str(current_keyboard) != str(reaction_only_keyboard):
                try:
                    await callback.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reaction_only_keyboard
                    )
                    logger.info(f"Successfully updated keyboard for message {message_id} to reaction_only")
                except Exception as e:
                    logger.warning(f"Failed to update keyboard for message {message_id}: {e}")
            else:
                logger.info(f"Keyboard for message {message_id} already has reaction_only state, skipping update")
        else:
            # Если нет users_jokes_id, удаляем всю клавиатуру
            current_keyboard = callback.message.reply_markup
            if current_keyboard is not None:
                try:
                    await callback.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=None
                    )
                    logger.info(f"Successfully removed keyboard for message {message_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove keyboard for message {message_id}: {e}")
            else:
                logger.info(f"Message {message_id} already has no keyboard, skipping update")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling next joke callback for user {user_id} with data {callback.data}: {str(e)}")
        await callback.answer(f"Произошла ошибка при получении анекдота (данные: {callback.data})", show_alert=True)

def register_handlers(dp):
    dp.include_router(router)