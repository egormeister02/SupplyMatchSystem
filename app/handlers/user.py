"""
User registration and authorization handlers
"""

import logging
import re
from datetime import datetime

from aiogram import Router, F, Bot, types
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.services import get_db_session, DBService
from app.states.states import RegistrationStates, SupplierSearchStates
from app.states.state_config import get_state_config
from app.keyboards.inline import (
    get_main_user_menu_keyboard,
    get_back_keyboard
)
from app.utils.message_utils import remove_keyboard_from_context, send_supplier_card

# Initialize router
router = Router()

# Validation patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
PHONE_PATTERN = re.compile(r'^\+?[0-9]{10,15}$')  # International phone numbers

def is_valid_email(email):
    """Проверяет валидность email с помощью простого регулярного выражения"""
    if not email:
        return False
    return bool(EMAIL_PATTERN.match(email))

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    """Handler for /start command"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if user exists in database
    async with get_db_session() as session:
        db_service = DBService(session)
        user_exists = await db_service.check_user_exists(user_id)
        
    if user_exists:
        # User exists, show main menu
        await message.answer(
            f"Добро пожаловать в меню, {message.from_user.first_name}! Выберите действие:",
            reply_markup=get_main_user_menu_keyboard()
        )
        # Reset any active states
        await state.clear()
    else:
        # User doesn't exist, start registration
        await message.answer(
            "Добро пожаловать! Для начала работы необходимо зарегистрироваться."
        )
        
        # Получаем конфигурацию для состояния ввода имени
        first_name_config = get_state_config(RegistrationStates.waiting_first_name)
        
        await message.answer(
            first_name_config["text"],
            reply_markup=first_name_config.get("markup")
        )
        
        # Set state to waiting for first name
        await state.set_state(RegistrationStates.waiting_first_name)

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
        await callback.message.answer(
            "Регистрация успешно завершена! Добро пожаловать!",
            reply_markup=get_main_user_menu_keyboard()
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
async def handle_suppliers_list(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки 'База поставщиков'.
    Показывает список категорий для выбора.
    """
    await callback.answer()
    
    # Получаем основные категории из базы
    async with get_db_session() as session:
        db_service = DBService(session)
        main_categories = await db_service.get_main_categories()
    
    # Формируем сообщение со списком категорий
    text = "Выберите категорию (введите номер):\n\n"
    
    for i, category in enumerate(main_categories, 1):
        text += f"{i}. {category['name']}\n"
    
    # Добавляем кнопку "Назад"
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_action:suppliers")]
    ])
    
    # Сохраняем категории в состояние
    await state.update_data(main_categories=main_categories)
    
    # Отправляем сообщение и устанавливаем состояние
    await callback.message.answer(text, reply_markup=markup)
    await state.set_state(SupplierSearchStates.waiting_category)

# Обработчик для всех текстовых сообщений в состоянии ожидания ввода категории
@router.message(SupplierSearchStates.waiting_category)
async def process_supplier_category(message: Message, state: FSMContext, bot: Bot):
    """
    Обработчик ввода номера категории поставщиков.
    """
    # Получаем текст сообщения
    category_text = message.text.strip()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    main_categories = state_data.get("main_categories", [])
    
    # Проверяем ввод на число
    try:
        category_number = int(category_text)
        
        # Проверяем диапазон
        if not main_categories or category_number < 1 or category_number > len(main_categories):
            await message.answer(
                f"Пожалуйста, введите корректный номер категории от 1 до {len(main_categories)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="suppliers_list")]
                ])
            )
            return
        
        # Получаем выбранную категорию
        selected_category = main_categories[category_number - 1]["name"]
        
        # Сохраняем выбранную категорию
        await state.update_data(main_category=selected_category)
        
        # Получаем подкатегории из базы
        async with get_db_session() as session:
            db_service = DBService(session)
            subcategories = await db_service.get_subcategories(selected_category)
        
        # Если подкатегорий нет
        if not subcategories:
            await message.answer(
                f"В категории '{selected_category}' нет подкатегорий.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
                ])
            )
            return
        
        # Формируем сообщение со списком подкатегорий
        text = f"Выбрана категория: {selected_category}\n\nВыберите подкатегорию (введите номер):\n\n"
        
        for i, subcategory in enumerate(subcategories, 1):
            text += f"{i}. {subcategory['name']}\n"
        
        # Добавляем кнопку "Назад"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
        ])
        
        # Сохраняем подкатегории в состояние
        await state.update_data(subcategories=subcategories)
        
        # Отправляем сообщение и устанавливаем состояние
        await message.answer(text, reply_markup=markup)
        await state.set_state(SupplierSearchStates.waiting_subcategory)
        
    except ValueError:
        # Если ввод не число, сообщаем об ошибке
        await message.answer(
            f"Пожалуйста, введите номер категории числом от 1 до {len(main_categories)}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="suppliers_list")]
            ])
        )

# Обработчик для всех текстовых сообщений в состоянии ожидания ввода подкатегории
@router.message(SupplierSearchStates.waiting_subcategory)
async def process_supplier_subcategory(message: Message, state: FSMContext, bot: Bot):
    """
    Обработчик ввода номера подкатегории поставщиков.
    """
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
            await message.answer(
                f"Пожалуйста, введите корректный номер подкатегории от 1 до {len(subcategories)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
                ])
            )
            return
        
        # Получаем выбранную подкатегорию
        selected_subcategory = subcategories[subcategory_number - 1]
        subcategory_id = selected_subcategory["id"]
        subcategory_name = selected_subcategory["name"]
        
        # Получаем список поставщиков для выбранной подкатегории
        async with get_db_session() as session:
            db_service = DBService(session)
            query = """
                SELECT * FROM suppliers 
                WHERE category_id = :category_id AND status = 'pending'
                ORDER BY created_at DESC
            """
            result = await db_service.execute_query(query, {"category_id": subcategory_id})
            suppliers = [dict(row) for row in result.mappings().fetchall()]
        
        # Если поставщиков нет
        if not suppliers:
            await message.answer(
                f"В подкатегории '{subcategory_name}' нет поставщиков.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
                ])
            )
            return
        
        # Выводим сообщение с количеством найденных поставщиков
        await message.answer(
            f"Найдено поставщиков в подкатегории '{subcategory_name}': {len(suppliers)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
            ])
        )
        
        # Получаем полные данные о поставщиках
        supplier_ids = [supplier["id"] for supplier in suppliers]
        
        full_suppliers = []
        for supplier_id in supplier_ids:
            supplier_data = await db_service.get_supplier_by_id(supplier_id)
            if supplier_data:
                full_suppliers.append(supplier_data)
        
        # Сохраняем список поставщиков и текущий индекс в состояние
        await state.update_data(
            suppliers=full_suppliers,
            current_index=0
        )
        
        # Если есть поставщики, отображаем первого
        if full_suppliers:
            current_supplier = full_suppliers[0]
            total_suppliers = len(full_suppliers)
            
            # Создаем клавиатуру для навигации
            keyboard = [
                [
                    InlineKeyboardButton(text="◀️", callback_data="prev_supplier"),
                    InlineKeyboardButton(text=f"1/{total_suppliers}", callback_data="supplier_info"),
                    InlineKeyboardButton(text="▶️", callback_data="next_supplier")
                ],
                [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
            ]
            
            # Отправляем карточку первого поставщика
            await send_supplier_card(
                bot=bot,
                chat_id=message.chat.id,
                supplier=current_supplier,
                inline_keyboard=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
            # Устанавливаем состояние просмотра поставщиков
            await state.set_state(SupplierSearchStates.viewing_suppliers)
        else:
            # Если по какой-то причине не удалось получить полные данные
            await message.answer(
                "Не удалось загрузить данные о поставщиках. Пожалуйста, попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
                ])
            )
            # Сбрасываем состояние
            await state.clear()
        
    except ValueError:
        # Если ввод не число, сообщаем об ошибке
        await message.answer(
            f"Пожалуйста, введите номер подкатегории числом от 1 до {len(subcategories)}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
            ])
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
    
    # Вычисляем новый индекс (с циклическим переходом)
    new_index = (current_index + 1) % len(suppliers)
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=new_index)
    
    # Получаем данные о новом поставщике
    current_supplier = suppliers[new_index]
    total_suppliers = len(suppliers)
    
    # Создаем клавиатуру для навигации
    keyboard = [
        [
            InlineKeyboardButton(text="◀️", callback_data="prev_supplier"),
            InlineKeyboardButton(text=f"{new_index+1}/{total_suppliers}", callback_data="supplier_info"),
            InlineKeyboardButton(text="▶️", callback_data="next_supplier")
        ],
        [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
    ]
    
    # Отправляем или редактируем карточку поставщика
    await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=current_supplier,
        inline_keyboard=InlineKeyboardMarkup(inline_keyboard=keyboard),
        message_id=callback.message.message_id
    )

@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data == "prev_supplier")
async def prev_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к предыдущему поставщику"""
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("suppliers", [])
    current_index = state_data.get("current_index", 0)
    
    # Вычисляем новый индекс (с циклическим переходом)
    new_index = (current_index - 1) % len(suppliers)
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=new_index)
    
    # Получаем данные о новом поставщике
    current_supplier = suppliers[new_index]
    total_suppliers = len(suppliers)
    
    # Создаем клавиатуру для навигации
    keyboard = [
        [
            InlineKeyboardButton(text="◀️", callback_data="prev_supplier"),
            InlineKeyboardButton(text=f"{new_index+1}/{total_suppliers}", callback_data="supplier_info"),
            InlineKeyboardButton(text="▶️", callback_data="next_supplier")
        ],
        [InlineKeyboardButton(text="Назад к категориям", callback_data="suppliers_list")]
    ]
    
    # Отправляем или редактируем карточку поставщика
    await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=current_supplier,
        inline_keyboard=InlineKeyboardMarkup(inline_keyboard=keyboard),
        message_id=callback.message.message_id
    )

@router.callback_query(SupplierSearchStates.viewing_suppliers, F.data == "supplier_info")
async def supplier_info(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия на информацию о текущем поставщике"""
    await callback.answer("Это текущий номер поставщика из общего количества")

# Обработчик на случай, если пользователь хочет вернуться назад
@router.callback_query(F.data == "suppliers_list", (F.state == SupplierSearchStates.waiting_category) | (F.state == SupplierSearchStates.waiting_subcategory) | (F.state == SupplierSearchStates.viewing_suppliers))
async def handle_back_to_suppliers_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для возврата к списку категорий"""
    await callback.answer()
    await handle_suppliers_list(callback, bot, state)

def register_handlers(dp):
    dp.include_router(router)