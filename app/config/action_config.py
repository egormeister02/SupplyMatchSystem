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
    get_main_user_menu_keyboard
)

# Конфигурация действий меню
action_config = {
    "main_menu": {
        "text": "Главное меню. Выберите нужный раздел:",
        "markup": get_main_user_menu_keyboard(),
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
        "text": "Раздел избранного (в разработке)",
        "markup": get_main_user_menu_keyboard(),
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
        "markup": get_main_user_menu_keyboard()
    }
}

def get_action_config(action):
    """Возвращает конфигурацию для указанного действия"""
    if action in action_config:
        return action_config[action]
    return None

# Обновление маркапов после создания функций в inline.py
def update_action_markups():
    """Обновляет маркапы для действий после инициализации функций в inline.py"""
    # Убедимся, что импорты успешно загружены
    try:
        from app.keyboards.inline import get_back_keyboard, get_keyboard_with_back
        
        # Обновляем маркапы для действий, где они не заданы
        for action_name, config in action_config.items():
            if config.get("markup") is None and config.get("parent") is not None:
                parent = config.get("parent")
                config["markup"] = get_back_keyboard(parent, is_state=False)
        
        # Обновляем маркап для suppliers_list с кнопками категорий
        if "suppliers_list" in action_config:
            action_config["suppliers_list"]["markup"] = get_keyboard_with_back(
                [
                    InlineKeyboardButton(text="Электроника", callback_data="suppliers_electronics"),
                    InlineKeyboardButton(text="Продукты питания", callback_data="suppliers_food"),
                ],
                back_target="main_menu",
                is_state=False,
                row_width=1
            )
    except ImportError:
        # Импорты еще не доступны, это нормально при первой загрузке
        pass 