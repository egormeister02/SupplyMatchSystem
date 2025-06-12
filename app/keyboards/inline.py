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
            [InlineKeyboardButton(text="Поставщики", callback_data="suppliers")],
            [InlineKeyboardButton(text="Заявки", callback_data="requests_list")],
            [InlineKeyboardButton(text="Избранное", callback_data="favorites_list")],
            [InlineKeyboardButton(text="Помощь", callback_data="help_action")]
        ]
    )

def get_main_admin_menu_keyboard():
    """Main menu for admin with 'Отчет' и командами управления админами"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поставщики", callback_data="suppliers")],
            [InlineKeyboardButton(text="Заявки", callback_data="requests_list")],
            [InlineKeyboardButton(text="Избранное", callback_data="favorites_list")],
            [InlineKeyboardButton(text="Отчет", callback_data="admin_report")]
        ]
    )

def get_main_menu_keyboard_by_role(role):
    if role == "admin":
        return get_main_admin_menu_keyboard()
    return get_main_user_menu_keyboard()

# Универсальные функции для кнопок "Назад"

def get_back_button(back_target, is_state=True, button_text="Назад", state_group=None):
    """
    Универсальная кнопка "Назад", которая работает как с состояниями, так и с действиями
    
    Args:
        back_target (str or State): Имя состояния или действия, или объект State для возврата
        is_state (bool): True, если это состояние, False, если действие
        button_text (str): Текст на кнопке, по умолчанию "Назад"
        state_group (str, optional): Название группы состояний (например, "RegistrationStates", "SupplierCreationStates")
                                    Если None и is_state=True, автоматически определит группу из имени состояния
    
    Returns:
        InlineKeyboardButton: Кнопка "Назад" с соответствующим callback_data
    """
    if is_state:
        # Проверяем, является ли back_target объектом State
        if hasattr(back_target, '__class__') and back_target.__class__.__name__ == 'State':
            # Получаем имя модуля и класса состояния
            module_name = back_target.__module__.split('.')[-1]
            class_name = back_target.__class__.__qualname__
            state_name = back_target.state
            
            # Формируем callback_data с полным путем к состоянию
            callback_data = f"back_to_state:{state_name}"
        else:
            # Если группа не указана, используем значение по умолчанию
            if state_group is None:
                # Определяем группу по имени состояния
                if isinstance(back_target, str) and back_target.startswith("waiting_"):
                    # Для состояния waiting_phone проверяем, относится ли оно к SupplierCreationStates
                    # или RegistrationStates на основе контекста и имени
                    if back_target in ["waiting_phone", "waiting_email", "waiting_contact"]:
                        # Эти состояния могут быть как в SupplierCreationStates, так и в RegistrationStates
                        state_group = "SupplierCreationStates"
                    else:
                        # Для других состояний предполагаем, что они в SupplierCreationStates
                        state_group = "SupplierCreationStates"
                else:
                    # Для других форматов имен состояний предполагаем, что они в RegistrationStates
                    state_group = "RegistrationStates"
            
            callback_data = f"back_to_state:{state_group}:{back_target}"
    else:
        callback_data = f"back_to_action:{back_target}"
    
    return InlineKeyboardButton(text=button_text, callback_data=callback_data)

def get_back_keyboard(back_target, is_state=True, button_text="Назад", state_group=None):
    """
    Универсальная клавиатура только с кнопкой "Назад", работающая как с состояниями, так и с действиями
    
    Args:
        back_target (str): Имя состояния или действия для возврата
        is_state (bool): True, если это состояние, False, если действие
        button_text (str): Текст на кнопке, по умолчанию "Назад"
        state_group (str, optional): Название группы состояний (например, "RegistrationStates", "SupplierCreationStates")
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой "Назад"
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [get_back_button(back_target, is_state, button_text, state_group)]
        ]
    )

def get_keyboard_with_back(buttons, back_target, is_state=True, row_width=1, button_text="Назад", state_group=None):
    """
    Универсальная функция для создания клавиатуры с кнопками и кнопкой "Назад"
    
    Args:
        buttons (list): Список кнопок (InlineKeyboardButton)
        back_target (str): Имя состояния или действия для возврата
        is_state (bool): True, если это состояние, False, если действие
        row_width (int): Количество кнопок в строке (кроме кнопки "Назад")
        button_text (str): Текст на кнопке "Назад", по умолчанию "Назад"
        state_group (str, optional): Название группы состояний (например, "RegistrationStates", "SupplierCreationStates")
    
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
    keyboard.append([get_back_button(back_target, is_state, button_text, state_group)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_report_period_keyboard(callback_prefix: str, back_target: str, back_button_text: str = "Назад"):
    """
    Универсальная клавиатура выбора периода для отчётов.
    Args:
        callback_prefix (str): Префикс для callback_data (например, 'report_table_reviews_period')
        back_target (str): Куда возвращаться по кнопке назад
        back_button_text (str): Текст кнопки назад
    Returns:
        InlineKeyboardMarkup
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 месяц", callback_data=f"{callback_prefix}:1")],
            [InlineKeyboardButton(text="3 месяца", callback_data=f"{callback_prefix}:3")],
            [InlineKeyboardButton(text="6 месяцев", callback_data=f"{callback_prefix}:6")],
            [InlineKeyboardButton(text="12 месяцев", callback_data=f"{callback_prefix}:12")],
            [InlineKeyboardButton(text="Все данные", callback_data=f"{callback_prefix}:all")],
            [get_back_button(back_target, is_state=False, button_text=back_button_text)]
        ]
    )

