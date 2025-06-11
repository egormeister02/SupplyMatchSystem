"""
User registration and authorization handlers
"""

import logging
import re
from datetime import datetime
from typing import Union

from aiogram import Router, F, Bot, types
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services import get_db_session, DBService
from app.states.states import RegistrationStates, SupplierSearchStates, SupplierCreationStates, RequestCreationStates
from app.states.state_config import get_state_config
from app.keyboards.inline import (
    get_main_menu_keyboard_by_role,
    get_back_keyboard
)
from app.utils.message_utils import remove_keyboard_from_context, send_supplier_card, remove_previous_keyboard
from app.config.config import get_admin_chat_id
from app.config.action_config import get_action_config
from app.config.logging import app_logger

# Initialize router with higher priority for commands
router = Router(name="user_commands")

# Validation patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
PHONE_PATTERN = re.compile(r'^\+?[0-9]{10,15}$')  # International phone numbers

def is_valid_email(email):
    """Проверяет валидность email с помощью простого регулярного выражения"""
    if not email:
        return False
    return bool(EMAIL_PATTERN.match(email))

# Explicitly set start command handler
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    app_logger.info(f"[START] /start called by user {message.from_user.id}")
    user_id = message.from_user.id
    username = message.from_user.username
    try:
        # Check if user exists in database
        user_exists = await DBService.check_user_exists_static(user_id)
        app_logger.info(f"[START] user_exists={user_exists}")

        # Получаем роль пользователя (если есть)
        user_role = None
        user_data = None
        if user_exists:
            async with get_db_session() as session:
                db_service = DBService(session)
                user_data = await db_service.get_user_by_id(user_id)
                app_logger.info(f"[START] user_data from DB: {user_data}")
                user_role = user_data.get("role") if user_data else None
                app_logger.info(f"[START] user_role={user_role}")

        if user_exists:
            # User exists, show main menu
            kb_message = await message.answer("Возвращаемся к меню", reply_markup=ReplyKeyboardRemove())
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=kb_message.message_id)
            except Exception as e:
                app_logger.error(f"[START] Ошибка при удалении сообщения: {str(e)}")
            main_menu_markup = get_main_menu_keyboard_by_role(user_role)
            app_logger.info(f"[START] Sending main menu, role={user_role}")
            await message.answer(
                f"Добро пожаловать в меню, {message.from_user.first_name}! Выберите действие:",
                reply_markup=main_menu_markup
            )
            await state.clear()
            app_logger.info(f"[START] State cleared for user {user_id}")
        else:
            await message.answer(
                "Добро пожаловать! Для начала работы необходимо зарегистрироваться."
            )
            first_name_config = get_state_config(RegistrationStates.waiting_first_name)
            await message.answer(
                first_name_config["text"],
                reply_markup=first_name_config.get("markup")
            )
            await state.set_state(RegistrationStates.waiting_first_name)
            app_logger.info(f"[START] Set state to waiting_first_name for user {user_id}")
    except Exception as e:
        app_logger.error(f"[START] Exception in /start: {e}")
        import traceback
        app_logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка при запуске. Пожалуйста, попробуйте позже.")

# Registration flow handlers
@router.message(RegistrationStates.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext, bot: Bot):
    """Handle first name input during registration"""
    # Save first name to state
    await state.update_data(first_name=message.text)
    
    # Получаем конфигурацию для следующего состояния
    last_name_config = get_state_config(RegistrationStates.waiting_last_name)
    
    # Ask for last name
    await message.answer(
        last_name_config["text"],
        reply_markup=last_name_config.get("markup")
    )
    
    await state.set_state(RegistrationStates.waiting_last_name)

@router.message(RegistrationStates.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext, bot: Bot):
    """Handle last name input during registration"""
    # Save last name to state
    await state.update_data(last_name=message.text)
    
    # Получаем конфигурацию для следующего состояния
    email_config = get_state_config(RegistrationStates.waiting_email)

    await remove_keyboard_from_context(bot, message)
    
    # Ask for email with skip option and back button
    await message.answer(
        email_config["text"],
        reply_markup=email_config.get("markup")
    )
    
    await state.set_state(RegistrationStates.waiting_email)

@router.message(RegistrationStates.waiting_email)
async def process_email(message: Message, state: FSMContext, bot: Bot):
    """Handle email input during registration"""
    email = message.text.strip()
    
    # Validate email with simple regex
    if not is_valid_email(email):
        # Get configuration for email state
        email_config = get_state_config(RegistrationStates.waiting_email)
        await message.answer(email_config["error_text"], reply_markup=email_config.get("markup"))
        return
    
    # Save email to state
    await state.update_data(email=email)
    
    # Get configuration for contact state
    contact_config = get_state_config(RegistrationStates.waiting_contact)
    
    # Ask for contact with custom keyboard
    await message.answer(
        contact_config["text"],
        reply_markup=contact_config.get("markup")
    )
    
    # Set state to waiting for contact
    await state.set_state(RegistrationStates.waiting_contact)

# Добавляем функцию для очистки клавиатуры при смене состояния
async def clear_reply_keyboard(chat_id: int, bot: Bot):
    """Отправляет пустое сообщение с ReplyKeyboardRemove для очистки клавиатуры"""
    try:
        message = await bot.send_message(
            chat_id=chat_id, 
            text="\u200B",  # Zero-width space
            reply_markup=ReplyKeyboardRemove()
        )
        # Удаляем сообщение сразу после отправки
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при очистке клавиатуры: {e}")

@router.message(RegistrationStates.waiting_contact, F.contact)
async def process_contact_shared(message: Message, state: FSMContext, bot: Bot):
    """Handle contact share during registration"""
    # Save phone number to state
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    # Удаляем клавиатуру
    await message.answer("Контакт получен.", reply_markup=ReplyKeyboardRemove())
    
    # Show confirmation
    await show_registration_confirmation(message, state, bot)

@router.message(RegistrationStates.waiting_contact, F.text == "Пропустить")
async def process_contact_skipped(message: Message, state: FSMContext, bot: Bot):
    """Handle skipped contact during registration"""
    # Save None as phone to state
    await state.update_data(phone=None)
    
    # Удаляем клавиатуру
    await message.answer("Ввод контакта пропущен.", reply_markup=ReplyKeyboardRemove())
    
    # Show confirmation
    await show_registration_confirmation(message, state, bot)

@router.message(RegistrationStates.waiting_contact, F.text == "Назад")
async def process_contact_back(message: Message, state: FSMContext, bot: Bot):
    """Handle back button press during phone input"""
    # Удаляем клавиатуру
    await message.answer("Возвращаемся назад...", reply_markup=ReplyKeyboardRemove())
    
    # Return to email input
    await state.set_state(RegistrationStates.waiting_email)
    
    # Получаем конфигурацию для состояния ввода email
    email_config = get_state_config(RegistrationStates.waiting_email)
    
    await message.answer(
        email_config["text"],
        reply_markup=email_config.get("markup")
    )

@router.message(RegistrationStates.waiting_contact)
async def process_contact(message: Message, state: FSMContext, bot: Bot):
    """Handle phone number input during registration"""
    # Validate phone number format
    phone = message.text.strip()
    
    if not PHONE_PATTERN.match(phone):
        # Получаем конфигурацию текущего состояния для сообщения об ошибке
        contact_config = get_state_config(RegistrationStates.waiting_contact)
        
        await message.answer(
            contact_config.get("error_text"),
            reply_markup=contact_config.get("markup")
        )
        return
    
    # Save phone to state
    await state.update_data(phone=phone)
    
    # Удаляем клавиатуру
    await message.answer("Номер телефона получен.", reply_markup=ReplyKeyboardRemove())
    
    # Show confirmation
    await show_registration_confirmation(message, state, bot)

@router.callback_query(RegistrationStates.confirm_registration, F.data == "confirm")
async def confirm_registration(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle registration confirmation"""
    await callback.answer()
    
    # Get all data from state
    user_data = await state.get_data()
    
    # Get user info from Telegram
    user_id = callback.from_user.id
    username = callback.from_user.username
    
    # Форматируем username в правильном формате с @
    if username and not username.startswith('@'):
        username = '@' + username
    
    # Save user to database
    try:
        async with get_db_session() as session:
            db_service = DBService(session)
            
            save_result = await db_service.save_user(
                user_id,
                username,  # Уже отформатированный с @
                user_data.get("first_name", ""),
                user_data.get("last_name", ""),
                user_data.get("email"),  # Will be None if skipped
                user_data.get("phone")   # Will be None if skipped
            )
            
            if not save_result:
                raise Exception("unsuccessful save user")
        
        # Если все прошло успешно, показываем главное меню
        
        # Remove keyboard from confirmation message
        await remove_keyboard_from_context(bot, callback)
        
        # Show main menu
        async with get_db_session() as session:
            db_service = DBService(session)
            user_data = await db_service.get_user_by_id(callback.from_user.id)
            user_role = user_data.get("role") if user_data else None
        main_menu_markup = get_main_menu_keyboard_by_role(user_role)
        await callback.message.answer(
            "Регистрация успешно завершена! Добро пожаловать!",
            reply_markup=main_menu_markup
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        # Логируем ошибку
        logging.error(f"Error during saving user to database {user_id} ({username}): {e}")
        
        # Удаляем клавиатуру подтверждения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем пользователю об ошибке
        await callback.message.answer(
            "К сожалению, произошла ошибка при регистрации. Пожалуйста, попробуйте позже или свяжитесь с поддержкой.",
            reply_markup=get_back_keyboard("waiting_first_name", is_state=True)
        )
        
        # Не очищаем state, чтобы пользователь мог вернуться и попробовать зарегистрироваться снова

# Helper functions
async def show_registration_confirmation(message: Message, state: FSMContext, bot: Bot):
    """Show registration confirmation with collected data"""
    # Сначала убедимся, что клавиатура удалена
    await clear_reply_keyboard(message.chat.id, bot)
    
    # Дальше продолжаем обычную логику
    # Get data from state
    user_data = await state.get_data()
    
    # Create confirmation message
    confirmation_text = "Пожалуйста, проверьте введенные данные:\n\n"
    confirmation_text += f"Имя: {user_data.get('first_name', '')}\n"
    confirmation_text += f"Фамилия: {user_data.get('last_name', '')}\n"
    
    # Email display logic
    email = user_data.get("email")
    if email:
        confirmation_text += f"Email: {email}\n"
    else:
        confirmation_text += "Email: Не указан\n"
    
    # Phone display logic
    phone = user_data.get("phone")
    if phone:
        confirmation_text += f"Телефон: {phone}\n"
    else:
        confirmation_text += "Телефон: Не указан\n"
    
    # Set state to confirmation
    await state.set_state(RegistrationStates.confirm_registration)
    
    # Получаем конфигурацию для состояния подтверждения
    confirm_config = get_state_config(RegistrationStates.confirm_registration)
    
    # Показываем подтверждение с клавиатурой из конфигурации
    await message.answer(confirmation_text, reply_markup=confirm_config.get("markup"))

# Обновленный код для выбора категорий поставщиков
@router.callback_query(F.data == "suppliers_list")
async def handle_suppliers_list(callback: Union[CallbackQuery, Message], bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки 'База поставщиков'.
    Показывает список категорий для выбора.
    """
    # Проверяем тип входящего объекта и вызываем answer() только если это CallbackQuery
    is_callback = isinstance(callback, CallbackQuery)
    if is_callback:
        await callback.answer()
    
    try:
        # Получаем основные категории из базы, используя статический метод
        main_category_config = get_state_config(SupplierSearchStates.waiting_category)
        
        categories_text = await main_category_config["text_func"](state)
        
        # В зависимости от типа входящего объекта, выбираем метод отправки
        if is_callback:
            await callback.message.answer(
                categories_text,
                reply_markup=main_category_config.get("markup")
            )
        else:
            await callback.answer(
                categories_text,
                reply_markup=main_category_config.get("markup")
            )
        
        await state.set_state(SupplierSearchStates.waiting_category)
        
    except Exception as e:
        logging.error(f"Ошибка при получении категорий: {str(e)}")
        
        # В зависимости от типа входящего объекта, выбираем метод отправки
        if is_callback:
            await callback.message.answer(
                "Произошла ошибка при загрузке категорий. Пожалуйста, попробуйте позже.",
                reply_markup=get_main_menu_keyboard_by_role(None)
            )
        else:
            await callback.answer(
                "Произошла ошибка при загрузке категорий. Пожалуйста, попробуйте позже.",
                reply_markup=get_main_menu_keyboard_by_role(None)
            )

# Обработчик для всех текстовых сообщений в состоянии ожидания ввода категории
@router.message(SupplierSearchStates.waiting_category)
async def process_supplier_category(message: Message, state: FSMContext, bot: Bot):
    
    try:
        category_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        state_data = await state.get_data()
        main_categories = state_data.get("main_categories", [])
        
        if not main_categories or category_number < 1 or category_number > len(main_categories):

            main_category_config = get_state_config(SupplierSearchStates.waiting_main_category)
            categories_text = await main_category_config["text_func"](state)
            
            await message.answer(
                f"{main_category_config['error_text']}\n\n{categories_text}",
                reply_markup=main_category_config.get("markup")
            )
            return
        
        selected_category = main_categories[category_number - 1]["name"]
        
        await state.update_data(main_category=selected_category)
        
        subcategory_config = get_state_config(SupplierSearchStates.waiting_subcategory)
        
        subcategories_text, success = await subcategory_config["text_func"](selected_category, state)
        
        if not success:
            await message.answer(
                subcategories_text,
                reply_markup=main_category_config.get("markup")
            )
            return
        
        await message.answer(
            subcategories_text,
            reply_markup=subcategory_config.get("markup")
        )
        
        await state.set_state(SupplierSearchStates.waiting_subcategory)
            
    except ValueError:

        main_category_config = get_state_config(SupplierSearchStates.waiting_main_category)
        categories_text = await main_category_config["text_func"](state)
        
        await message.answer(
            f"{main_category_config['error_text']}\n\n{categories_text}",
            reply_markup=main_category_config.get("markup")
        )

# Добавляем обработчики для навигации между поставщиками
@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data == "next_supplier")
async def next_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к следующему поставщику"""
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("suppliers", [])
    current_index = state_data.get("current_index", 0)
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Вычисляем новый индекс (с циклическим переходом)
    new_index = (current_index + 1) % len(suppliers)
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=new_index)
    
    # Получаем данные о новом поставщике
    current_supplier = suppliers[new_index]
    total_suppliers = len(suppliers)
    
    # Добавляем отладочное логирование для проверки видео
    if 'video' in current_supplier:
        video_data = current_supplier.get('video')
        logging.info(f"Видео для поставщика {current_supplier.get('id')} (next): {video_data}")
        
        # Проверяем и добавляем storage_path для видео, если необходимо
        if video_data and isinstance(video_data, dict) and 'file_path' in video_data and not 'storage_path' in video_data:
            video_data['storage_path'] = video_data['file_path']
            logging.info(f"Добавлен storage_path для видео: {video_data}")
    else:
        logging.info(f"У поставщика {current_supplier.get('id')} (next) отсутствует ключ 'video' в данных")
    
    # Получаем конфигурацию для состояния
    config = get_state_config(SupplierSearchStates.viewing_suppliers)
    keyboard = config["markup"]
    
    # Обновляем текст кнопки с текущим индексом
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data == "current_supplier":
                button.text = f"{new_index+1}/{total_suppliers}"
    
    # Удаляем сообщение с предыдущей клавиатурой, если ID известен
    if keyboard_message_id:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=keyboard_message_id
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении старой клавиатуры: {e}")
    
    # Удаляем все сообщения с медиа из предыдущей карточки
    for media_id in media_message_ids:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=media_id
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении медиа-сообщения {media_id}: {e}")
    
    # Отправляем карточку поставщика с клавиатурой
    message_ids = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=current_supplier,
        keyboard=keyboard,
        include_video=True  # Включаем видео в группу при просмотре всех фото
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=message_ids["keyboard_message_id"],
        media_message_ids=message_ids["media_message_ids"]
    )

@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data == "prev_supplier")
async def prev_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к предыдущему поставщику"""
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("suppliers", [])
    current_index = state_data.get("current_index", 0)
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Вычисляем новый индекс (с циклическим переходом)
    new_index = (current_index - 1) % len(suppliers)
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=new_index)
    
    # Получаем данные о новом поставщике
    current_supplier = suppliers[new_index]
    total_suppliers = len(suppliers)
    
    # Добавляем отладочное логирование для проверки видео
    if 'video' in current_supplier:
        video_data = current_supplier.get('video')
        logging.info(f"Видео для поставщика {current_supplier.get('id')} (prev): {video_data}")
        
        # Проверяем и добавляем storage_path для видео, если необходимо
        if video_data and isinstance(video_data, dict) and 'file_path' in video_data and not 'storage_path' in video_data:
            video_data['storage_path'] = video_data['file_path']
            logging.info(f"Добавлен storage_path для видео: {video_data}")
    else:
        logging.info(f"У поставщика {current_supplier.get('id')} (prev) отсутствует ключ 'video' в данных")
    
    # Получаем конфигурацию для состояния
    config = get_state_config(SupplierSearchStates.viewing_suppliers)
    keyboard = config["markup"]
    
    # Обновляем текст кнопки с текущим индексом
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data == "current_supplier":
                button.text = f"{new_index+1}/{total_suppliers}"
    
    # Удаляем сообщение с предыдущей клавиатурой, если ID известен
    if keyboard_message_id:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=keyboard_message_id
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении старой клавиатуры: {e}")
    
    # Удаляем все сообщения с медиа из предыдущей карточки
    for media_id in media_message_ids:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=media_id
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении медиа-сообщения {media_id}: {e}")
    
    # Отправляем карточку поставщика с клавиатурой
    message_ids = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=current_supplier,
        keyboard=keyboard,
        include_video=True  # Включаем видео в группу при просмотре всех фото
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=message_ids["keyboard_message_id"],
        media_message_ids=message_ids["media_message_ids"]
    )

@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data.startswith("back_to_state:"))
async def back_to_subcategories(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для возврата к выбору подкатегории"""
    await callback.answer()

    # Удаляем клавиатуру у карточки поставщика и у сообщения-носителя клавиатуры
    state_data = await state.get_data()
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    chat_id = callback.message.chat.id
    # Удаляем клавиатуру у сообщения-носителя, если оно не входит в media_message_ids
    if keyboard_message_id and keyboard_message_id not in media_message_ids:
        try:
            await remove_previous_keyboard(bot, keyboard_message_id, chat_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении клавиатуры у сообщения-носителя {keyboard_message_id}: {e}")
    # Удаляем клавиатуру у медиа-сообщений (например, у одиночного фото)
    for msg_id in media_message_ids:
        try:
            await remove_previous_keyboard(bot, msg_id, chat_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении клавиатуры у медиа сообщения {msg_id}: {e}")

    # Получаем данные из состояния
    main_category = state_data.get("main_category", "")
    
    # Возвращаемся к выбору подкатегории
    try:
        # Получаем подкатегории для выбранной основной категории
        subcategories = await DBService.get_subcategories_static(main_category)
        
        # Если подкатегорий нет
        if not subcategories:
            # Возвращаемся к выбору категории
            await handle_suppliers_list(callback, bot, state)
            return
        
        # Формируем сообщение со списком подкатегорий
        text = f"Выбрана категория: {main_category}\n\nВыберите подкатегорию (введите номер):\n\n"
        
        for i, subcategory in enumerate(subcategories, 1):
            text += f"{i}. {subcategory['name']}\n"
        
        # Сохраняем подкатегории в состояние
        await state.update_data(subcategories=subcategories)
        
        # Получаем конфигурацию для состояния
        config = get_state_config(SupplierSearchStates.waiting_subcategory)
        
        # Отправляем сообщение и устанавливаем состояние
        await callback.message.answer(text, reply_markup=config["markup"])
        await state.set_state(SupplierSearchStates.waiting_subcategory)
        
    except Exception as e:
        logging.error(f"Ошибка при возврате к подкатегориям: {str(e)}")
        await callback.message.answer(
            "Произошла ошибка при загрузке подкатегорий. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_menu_keyboard_by_role(None)
        )

# Обновляем обработчик для вывода списка поставщиков
@router.message(SupplierSearchStates.waiting_subcategory)
async def process_supplier_subcategory(message: Message, state: FSMContext, bot: Bot):
    """Обработчик ввода номера подкатегории поставщиков."""
    # Получаем текст сообщения
    subcategory_text = message.text.strip()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    subcategories = state_data.get("subcategories", [])
    selected_category = state_data.get("main_category", "")
    
    # Проверяем ввод на число
    try:
        subcategory_number = int(subcategory_text)
        
        # Проверяем диапазон
        if not subcategories or subcategory_number < 1 or subcategory_number > len(subcategories):
            config = get_state_config(SupplierSearchStates.waiting_subcategory)
            await message.answer(
                config["error_text"],
                reply_markup=config["markup"]
            )
            return
        
        # Получаем выбранную подкатегорию
        selected_subcategory = subcategories[subcategory_number - 1]
        subcategory_id = selected_subcategory["id"]
        subcategory_name = selected_subcategory["name"]
        
        try:
            # Получаем список поставщиков для выбранной подкатегории, используя статический метод
            supplier_ids = await DBService.get_suppliers_by_subcategory_static(subcategory_id)
            
            # Если поставщиков нет
            if not supplier_ids:
                config = get_state_config(SupplierSearchStates.waiting_subcategory)
                await message.answer(
                    f"В подкатегории '{subcategory_name}' нет поставщиков.",
                    reply_markup=config["markup"]
                )
                return
            
            # Выводим сообщение с количеством найденных поставщиков
            config = get_state_config(SupplierSearchStates.viewing_suppliers)
            
            # Получаем клавиатуру из конфигурации
            keyboard = config["markup"]
            
            # Обновляем текст кнопки с текущим индексом
            for row in keyboard.inline_keyboard:
                for button in row:
                    if button.callback_data == "current_supplier":
                        button.text = f"1/{len(supplier_ids)}"
            
            # Отправляем информационное сообщение
            await message.answer(
                f"Найдено поставщиков в подкатегории '{subcategory_name}': {len(supplier_ids)}"
            )
            
            # Обрабатываем поставщиков
            full_suppliers = []
            for supplier_id in supplier_ids:
                try:
                    # Проверяем, является ли supplier_id словарем или просто числом
                    sid = supplier_id.get('id') if isinstance(supplier_id, dict) else supplier_id
                    supplier_data = await DBService.get_supplier_by_id_static(sid)
                    if supplier_data:
                        full_suppliers.append(supplier_data)
                except Exception as e:
                    logging.error(f"Ошибка при получении данных поставщика {supplier_id}: {str(e)}")
                    continue
            
            # Если есть поставщики, отображаем первого
            if full_suppliers:
                current_supplier = full_suppliers[0]
                
                # Добавляем отладочное логирование для проверки наличия видео
                if 'video' in current_supplier:
                    video_data = current_supplier.get('video')
                    logging.info(f"Видео для поставщика {current_supplier.get('id')}: {video_data}")
                    
                    # Проверяем и добавляем storage_path для видео, если необходимо
                    if video_data and isinstance(video_data, dict) and 'file_path' in video_data and not 'storage_path' in video_data:
                        video_data['storage_path'] = video_data['file_path']
                        logging.info(f"Добавлен storage_path для видео: {video_data}")
                else:
                    logging.info(f"У поставщика {current_supplier.get('id')} отсутствует ключ 'video' в данных")
                
                # Отправляем карточку первого поставщика с клавиатурой
                # Функция send_supplier_card теперь возвращает словарь с ID сообщений
                message_ids = await send_supplier_card(
                    bot=bot,
                    chat_id=message.chat.id,
                    supplier=current_supplier,
                    keyboard=keyboard,
                    include_video=True  # Включаем видео в группу при просмотре всех фото
                )
                
                # Сохраняем список поставщиков, текущий индекс и ID сообщений в состоянии
                await state.update_data(
                    suppliers=full_suppliers,
                    current_index=0,
                    keyboard_message_id=message_ids["keyboard_message_id"],
                    media_message_ids=message_ids["media_message_ids"]
                )
                
                # Устанавливаем состояние просмотра поставщиков
                await state.set_state(SupplierSearchStates.viewing_suppliers)
            else:
                # Если нет ни одного поставщика с полными данными
                config = get_state_config(SupplierSearchStates.waiting_subcategory)
                await message.answer(
                    "Не удалось загрузить данные о поставщиках. Пожалуйста, попробуйте позже.",
                    reply_markup=config["markup"]
                )
        except Exception as e:
            # Обработка любых ошибок при работе с БД
            logging.error(f"Ошибка при получении поставщиков для подкатегории {subcategory_id}: {str(e)}")
            config = get_state_config(SupplierSearchStates.waiting_subcategory)
            await message.answer(
                "Произошла ошибка при загрузке поставщиков. Пожалуйста, попробуйте позже.",
                reply_markup=config["markup"]
            )
        
    except ValueError:
        # Если ввод не число, сообщаем об ошибке
        config = get_state_config(SupplierSearchStates.waiting_subcategory)
        await message.answer(
            config["error_text"],
            reply_markup=config["markup"]
        )
    except Exception as e:
        # Обработка любых других ошибок
        logging.error(f"Неожиданная ошибка при обработке подкатегории: {str(e)}")
        config = get_state_config(SupplierSearchStates.waiting_subcategory)
        await message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте позже или выберите другую подкатегорию.",
            reply_markup=config["markup"]
        )

@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data == "current_supplier")
async def handle_current_supplier(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия на кнопку с текущим номером поставщика"""
    # Просто отвечаем на колбэк без действий
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handler for /help command"""
    help_text = (
        "Доступные команды:\n"
        "/start - начать работу с ботом\n"
        "/help - показать справку"
    )
    await message.answer(help_text)

def register_handlers(dp):
    """Register all handlers from this module"""
    dp.include_router(router)
