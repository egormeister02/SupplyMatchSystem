"""
Конфигурация для действий без состояний.
Аналогично state_config, но для действий, которые не требуют состояний.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Импортируем функции для клавиатур после их обновления
# Эти импорты будут работать после обновления файла keyboards/inline.py
from app.keyboards.inline import (
    get_back_keyboard,
    get_keyboard_with_back,
    get_back_button,
    get_main_user_menu_keyboard,
    get_main_admin_menu_keyboard
)

def get_main_menu_keyboard_by_role(role):
    if role == "admin":
        return get_main_admin_menu_keyboard()
    return get_main_user_menu_keyboard()

# Конфигурация действий меню
action_config = {
    "main_menu": {
        "text": "Главное меню. Выберите нужный раздел:",
        "markup_func": get_main_menu_keyboard_by_role,
        "parent": None,  # У главного меню нет родителя
    },
    
    "suppliers": {
        "text": "Выберите действие с поставщиками:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Создать поставщика", callback_data="create_supplier")],
                [InlineKeyboardButton(text="Мои поставщики", callback_data="view_my_suppliers")],
                [InlineKeyboardButton(text="База поставщиков", callback_data="suppliers_list")],
                [get_back_button("main_menu", is_state=False, button_text="Главное меню")]
            ]
        ),
        "parent": "main_menu",
    },
    
    "favorites_list": {
        "text": "Главное меню",
        "markup_func": get_main_menu_keyboard_by_role,
        "parent": "main_menu",
    },

    "requests_list": {
        "text": "Раздел заявок:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Создать заявку", callback_data="create_request")],
                [InlineKeyboardButton(text="Мои заявки", callback_data="my_requests")],
                [get_back_button("main_menu", is_state=False, button_text="Главное меню")]
            ]
        ),
        "parent": "main_menu",
    },

    "my_requests": {
        "text": "Ваши заявки:",
        "markup": get_back_keyboard("requests_list", is_state=False, button_text="Назад")
    },

    "help_action": {
        "text": "Добро пожаловать в раздел помощи!\n\n"
                "Здесь вы можете найти ответы на часто задаваемые вопросы и инструкции по использованию нашего бота.\n\n"
                "Если у вас остались вопросы, обратитесь к администратору.",
        "markup_func": get_main_menu_keyboard_by_role
    }
}

def get_action_config(action):
    """Возвращает конфигурацию для указанного действия"""
    if action in action_config:
        return action_config[action]
    return None

# Обновление маркапов после создания функций в inline.py

def update_action_markups():
    # Stub for backward compatibility
    pass
