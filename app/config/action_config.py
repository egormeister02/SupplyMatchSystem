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
    get_back_button
)

# Конфигурация действий меню
action_config = {
    "main_menu": {
        "text": "Главное меню. Выберите действие:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Поставщики", callback_data="suppliers_list")],
                [InlineKeyboardButton(text="Запросы", callback_data="requests_list")],
                [InlineKeyboardButton(text="Избранное", callback_data="favorites_list")],
                [InlineKeyboardButton(text="Помощь", callback_data="help_action")]
            ]
        ),
        "parent": None,  # У главного меню нет родителя
    },
    
    "suppliers_list": {
        "text": "Список поставщиков по категориям:",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "main_menu",
    },
    
    "suppliers_electronics": {
        "text": "Поставщики электроники:",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "suppliers_list",
    },
    
    "suppliers_food": {
        "text": "Поставщики продуктов питания:",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "suppliers_list",
    },
    
    "requests_list": {
        "text": "Ваши запросы:",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "main_menu",
    },
    
    "favorites_list": {
        "text": "Избранные поставщики:",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "main_menu",
    },
    
    "help_action": {
        "text": "Справка по работе с ботом:\n\n"
                "1. Выберите раздел в главном меню\n"
                "2. Для возврата назад используйте кнопку 'Назад'\n"
                "3. Для связи с поддержкой напишите /support",
        "markup": None,  # Будет заполнено после обновления inline.py
        "parent": "main_menu",
    },
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