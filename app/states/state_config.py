"""
Конфигурация для состояний бота.
Содержит тексты сообщений и клавиатуры для каждого состояния.
"""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from app.keyboards.inline import (
    get_back_keyboard,
    get_keyboard_with_back,
)

from app.states.states import RegistrationStates

# Конфигурация состояний регистрации
registration_config = {
    # Состояние ожидания имени
    RegistrationStates.waiting_first_name: {
        "text": "Введите ваше имя:",
        "markup": None,
        "back_state": None,  # Некуда возвращаться, это начальное состояние
    },
    
    # Состояние ожидания фамилии
    RegistrationStates.waiting_last_name: {
        "text": "Теперь введите вашу фамилию:",
        "markup": get_back_keyboard("waiting_first_name", is_state=True),
        "back_state": RegistrationStates.waiting_first_name,
    },
    
    # Состояние ожидания email
    RegistrationStates.waiting_email: {
        "text": "Теперь введите ваш email:",
        "markup": get_keyboard_with_back([
            InlineKeyboardButton(text="Пропустить", callback_data="skip")
        ], "waiting_last_name", is_state=True),
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
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
                [InlineKeyboardButton(text="Изменить данные", callback_data="edit")],
                [InlineKeyboardButton(text="Назад", callback_data="back")]
            ]
        ),
        "back_state": RegistrationStates.waiting_contact,
    },
}

# Функция получения конфигурации для состояния
def get_state_config(state):
    if state in registration_config:
        return registration_config[state]
    return None

# Функция получения предыдущего состояния
def get_previous_state(current_state):
    config = get_state_config(current_state)
    if config and "back_state" in config:
        return config["back_state"]
    return None 