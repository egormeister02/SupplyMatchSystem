"""
Inline keyboards for the bot
"""

from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# Registration keyboards
def get_skip_keyboard():
    """Keyboard with skip button for optional fields"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip")]
        ]
    )

def get_confirmation_keyboard():
    """Keyboard for registration data confirmation"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
            [InlineKeyboardButton(text="Изменить данные", callback_data="edit")]
        ]
    )

def get_contact_keyboard():
    """Keyboard with contact sharing button and skip option"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="Пропустить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Main menu keyboard
def get_main_user_menu_keyboard():
    """Main menu with all available actions"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поставщики", callback_data="suppliers_list")],
            [InlineKeyboardButton(text="Запросы", callback_data="requests_list")],
            [InlineKeyboardButton(text="Избранное", callback_data="favorites_list")],
            [InlineKeyboardButton(text="Помощь", callback_data="help_action")]
        ]
    )

# Универсальные функции для кнопок "Назад"

def get_back_button(back_target, is_state=True):
    """
    Универсальная кнопка "Назад", которая работает как с состояниями, так и с действиями
    
    Args:
        back_target (str): Имя состояния или действия для возврата
        is_state (bool): True, если это состояние, False, если действие
    
    Returns:
        InlineKeyboardButton: Кнопка "Назад" с соответствующим callback_data
    """
    prefix = "back_to_state:" if is_state else "back_to_action:"
    return InlineKeyboardButton(text="Назад", callback_data=f"{prefix}{back_target}")

def get_back_keyboard(back_target, is_state=True):
    """
    Универсальная клавиатура только с кнопкой "Назад", работающая как с состояниями, так и с действиями
    
    Args:
        back_target (str): Имя состояния или действия для возврата
        is_state (bool): True, если это состояние, False, если действие
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой "Назад"
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [get_back_button(back_target, is_state)]
        ]
    )

def get_keyboard_with_back(buttons, back_target, is_state=True, row_width=1):
    """
    Универсальная функция для создания клавиатуры с кнопками и кнопкой "Назад"
    
    Args:
        buttons (list): Список кнопок (InlineKeyboardButton)
        back_target (str): Имя состояния или действия для возврата
        is_state (bool): True, если это состояние, False, если действие
        row_width (int): Количество кнопок в строке (кроме кнопки "Назад")
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками и кнопкой "Назад"
    """
    keyboard = []
    row = []
    
    for i, button in enumerate(buttons):
        row.append(button)
        if (i + 1) % row_width == 0:
            keyboard.append(row)
            row = []
    
    if row:  # Add remaining buttons
        keyboard.append(row)
    
    # Add back button in the last row
    keyboard.append([get_back_button(back_target, is_state)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

