"""
User registration and authorization handlers
"""

import logging
import re
from datetime import datetime

from aiogram import Router, F, Bot, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.services import get_db_session, DBService
from app.states.states import RegistrationStates
from app.states.state_config import get_state_config
from app.keyboards.inline import (
    get_main_user_menu_keyboard,
    get_back_keyboard
)
from app.utils.message_utils import remove_keyboard_from_context

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

@router.message(RegistrationStates.waiting_contact, F.contact)
async def process_contact_shared(message: Message, state: FSMContext, bot: Bot):
    """Handle contact share during registration"""
    # Save phone number to state
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    # Show confirmation
    await show_registration_confirmation(message, state, bot)

@router.message(RegistrationStates.waiting_contact, F.text == "Пропустить")
async def process_contact_skipped(message: Message, state: FSMContext, bot: Bot):
    """Handle skipped contact during registration"""
    # Save None as phone to state
    await state.update_data(phone=None)
    
    # Show confirmation
    await show_registration_confirmation(message, state, bot)

@router.message(RegistrationStates.waiting_contact, F.text == "Назад")
async def process_contact_back(message: Message, state: FSMContext, bot: Bot):
    """Handle back button press during phone input"""
    # Return to email input
    await state.set_state(RegistrationStates.waiting_email)
    
    # Получаем конфигурацию для состояния ввода email
    email_config = get_state_config(RegistrationStates.waiting_email)
    
    await message.answer(
        "Вернемся назад. " + email_config["text"],
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
    
    # Save user to database
    try:
        async with get_db_session() as session:
            db_service = DBService(session)
            
            save_result = await db_service.save_user(
                user_id,
                username,
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

def register_handlers(dp):
    dp.include_router(router) 