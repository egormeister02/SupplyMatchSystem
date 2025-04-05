"""
Конфигурация для состояний бота.
Содержит тексты сообщений и клавиатуры для каждого состояния.
"""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from app.keyboards.inline import (
    get_skip_keyboard, 
    get_confirmation_keyboard, 
    get_back_keyboard,
    get_keyboard_with_back,
)

from app.states.states import RegistrationStates

# Конфигурация состояний регистрации
registration_config = {
    # Состояние ожидания имени
    RegistrationStates.waiting_first_name: {
        "text": "Как вас зовут? Введите ваше имя:",
        "markup": None,
        "back_state": None,  # Некуда возвращаться, это начальное состояние
    },
    
    # Состояние ожидания фамилии
    RegistrationStates.waiting_last_name: {
        "text": "Спасибо! Теперь введите вашу фамилию:",
        "markup": get_back_keyboard("back_to_waiting_first_name"),
        "back_state": RegistrationStates.waiting_first_name,
    },
    
    # Состояние ожидания email
    RegistrationStates.waiting_email: {
        "text": "Спасибо! Теперь введите ваш email:",
        "markup": get_keyboard_with_back([
            InlineKeyboardButton(text="Пропустить", callback_data="skip")
        ], "back_to_waiting_last_name"),
        "back_state": RegistrationStates.waiting_last_name,
        "error_text": "Пожалуйста, введите корректный email или нажмите 'Пропустить':",
    },
    
    # Состояние ожидания контакта
    RegistrationStates.waiting_contact: {
        "text": "Теперь вы можете поделиться своим номером телефона, ввести его вручную или пропустить этот шаг:",
        "markup": ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Поделиться своим", request_contact=True)],
                [KeyboardButton(text="Пропустить")],
                [KeyboardButton(text="Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        ),
        "back_state": RegistrationStates.waiting_email,
        "error_text": "Пожалуйста, введите корректный номер телефона в международном формате (например, +79001234567) или нажмите кнопку 'Поделиться своим' или 'Пропустить'.",
    },
    
    # Состояние подтверждения регистрации
    RegistrationStates.confirm_registration: {
        "text": "Пожалуйста, проверьте введенные данные:",
        "markup": get_keyboard_with_back([
            InlineKeyboardButton(text="Подтвердить", callback_data="confirm"),
            InlineKeyboardButton(text="Изменить данные", callback_data="edit")
        ], "back_to_waiting_contact"),
        "back_state": RegistrationStates.waiting_contact,
    },
}

# Функция получения конфигурации для состояния
def get_state_config(state):
    """
    Получить конфигурацию для указанного состояния
    
    Args:
        state: Состояние FSM
        
    Returns:
        dict: Конфигурация состояния или None, если конфигурация не найдена
    """
    if state in registration_config:
        return registration_config[state]
    return None

# Функция получения предыдущего состояния
def get_previous_state(current_state):
    """
    Получить предыдущее состояние для текущего
    
    Args:
        current_state: Текущее состояние FSM
        
    Returns:
        State: Предыдущее состояние или None, если предыдущего состояния нет
    """
    config = get_state_config(current_state)
    if config and "back_state" in config:
        return config["back_state"]
    return None 