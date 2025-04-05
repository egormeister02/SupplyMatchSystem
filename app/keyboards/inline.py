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
def get_main_menu_keyboard():
    """Main menu with all available actions"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мои запросы", callback_data="my_requests")],
            [InlineKeyboardButton(text="Найти поставщика", callback_data="find_supplier")],
            [InlineKeyboardButton(text="Избранное", callback_data="favorites")],
            [InlineKeyboardButton(text="Помощь", callback_data="help")]
        ]
    )

# Универсальная кнопка "Назад"
def get_back_button(callback_data="back"):
    """Return back button with specified callback_data"""
    return InlineKeyboardButton(text="Назад", callback_data=callback_data)

def get_back_keyboard(callback_data="back"):
    """Return keyboard with only back button"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [get_back_button(callback_data)]
        ]
    )

def get_keyboard_with_back(buttons, back_callback_data="back", row_width=1):
    """
    Create keyboard with provided buttons and add back button at the bottom.
    
    Args:
        buttons (list): List of InlineKeyboardButton objects
        back_callback_data (str): Callback data for back button
        row_width (int): Number of buttons per row (except back button)
        
    Returns:
        InlineKeyboardMarkup: Keyboard with buttons and back button
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
    keyboard.append([get_back_button(back_callback_data)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
