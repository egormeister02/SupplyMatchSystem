"""
Конфигурация для состояний бота.
Содержит тексты сообщений и клавиатуры для каждого состояния.
"""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from app.keyboards.inline import (
    get_back_keyboard,
    get_keyboard_with_back,
    get_back_button,
)

from app.states.states import RegistrationStates, SupplierCreationStates
from app.services import get_db_session, DBService

# Вспомогательные функции для формирования текстов
def format_numbered_list(items, start_text="", item_formatter=lambda i, idx: f"{idx}. {i}"):
    """
    Формирует нумерованный список из предоставленных элементов.
    
    Args:
        items (list): Список элементов для нумерации
        start_text (str): Начальный текст перед списком
        item_formatter (callable): Функция форматирования для каждого элемента
            Принимает элемент и его индекс, возвращает строку
    
    Returns:
        str: Форматированный текст с нумерованным списком
    """
    result = start_text + "\n\n" if start_text else ""
    
    for idx, item in enumerate(items, 1):
        result += f"{item_formatter(item, idx)}\n"
    
    return result

async def get_categories_text(state: FSMContext = None):
    """
    Получает и форматирует список категорий.
    
    Args:
        state (FSMContext, optional): Контекст состояния для сохранения категорий
    
    Returns:
        str: Форматированный текст со списком категорий
    """
    async with get_db_session() as session:
        db_service = DBService(session)
        main_categories = await db_service.get_main_categories()
    
    if state:
        await state.update_data(main_categories=main_categories)
    
    return format_numbered_list(
        main_categories,
        "Выберите основную категорию вашего продукта. Введите номер категории:",
        lambda cat, idx: f"{idx}. {cat['name']}"
    )

async def get_subcategories_text(category_name, state: FSMContext = None):
    """
    Получает и форматирует список подкатегорий для указанной категории.
    
    Args:
        category_name (str): Название категории
        state (FSMContext, optional): Контекст состояния для сохранения подкатегорий
    
    Returns:
        str: Форматированный текст со списком подкатегорий
        bool: Успешность получения подкатегорий
    """
    async with get_db_session() as session:
        db_service = DBService(session)
        subcategories = await db_service.get_subcategories(category_name)
    
    if not subcategories:
        return f"Для категории '{category_name}' не найдено подкатегорий. Пожалуйста, выберите другую категорию.", False
    
    if state:
        await state.update_data(subcategories=subcategories)
    
    return format_numbered_list(
        subcategories,
        f"Выбрана категория: {category_name}\n\nТеперь выберите подкатегорию вашего продукта. Введите номер подкатегории:",
        lambda subcat, idx: f"{idx}. {subcat['name']}"
    ), True

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
        "markup": get_back_keyboard("waiting_first_name", is_state=True, button_text="Изменить имя"),
        "back_state": RegistrationStates.waiting_first_name,
    },
    
    # Состояние ожидания email
    RegistrationStates.waiting_email: {
        "text": "Теперь введите ваш email:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_contact", is_state=True, button_text="Пропустить")],
                [get_back_button("waiting_last_name", is_state=True, button_text="Изменить фамилию")]
            ]
        ),
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
                [get_back_button("waiting_first_name", is_state=True, button_text="Изменить данные")],
                [get_back_button("waiting_contact", is_state=True, button_text="Назад к вводу контакта")]
            ]
        ),
        "back_state": RegistrationStates.waiting_contact,
    },
}

# Конфигурация для состояний создания поставщика
supplier_creation_config = {
    # Ввод названия компании
    SupplierCreationStates.waiting_company_name: {
        "text": "Введите название вашей компании:",
        "markup": get_back_keyboard("suppliers", is_state=False, button_text="Вернуться к меню поставщиков"),
        "back_state": None,  # Возврат в главное меню
    },
    
    # Выбор основной категории
    SupplierCreationStates.waiting_main_category: {
        "text_func": get_categories_text,  # Функция для динамического формирования текста
        "markup": get_back_keyboard("waiting_company_name", is_state=True, button_text="Изменить название компании"),
        "back_state": SupplierCreationStates.waiting_product_name,
        "error_text": "Пожалуйста, введите корректный номер категории из списка.",
    },
    
    # Выбор подкатегории
    SupplierCreationStates.waiting_subcategory: {
        "text_func": get_subcategories_text,  # Функция для динамического формирования текста
        "markup": get_back_keyboard("waiting_main_category", is_state=True, button_text="Выбрать другую категорию"),
        "back_state": SupplierCreationStates.waiting_main_category,
        "error_text": "Пожалуйста, введите корректный номер подкатегории из списка.",
    },
    
    # Ввод названия продукта
    SupplierCreationStates.waiting_product_name: {
        "text": "Введите название вашего основного продукта или услуги:",
        "markup": get_back_keyboard("waiting_subcategory", is_state=True, button_text="Назад к подкатегории"),
        "back_state": SupplierCreationStates.waiting_company_name,
    },
    
    # Подтверждение создания поставщика
    SupplierCreationStates.confirm_supplier_creation: {
        "text": "Пожалуйста, проверьте введенные данные о поставщике:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
                [get_back_button("waiting_company_name", is_state=True, button_text="Изменить данные")],
                [get_back_button("waiting_product_name", is_state=True, button_text="Назад к названию продукта")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_subcategory,
    },
}

# Функция получения конфигурации для состояния
def get_state_config(state):
    """
    Получает конфигурацию для указанного состояния.
    
    Args:
        state: Объект состояния из RegistrationStates или SupplierCreationStates
        
    Returns:
        dict: Конфигурация для указанного состояния или None
    """
    config = None
    
    if state in registration_config:
        config = registration_config[state]
    elif state in supplier_creation_config:
        config = supplier_creation_config[state]
        
    return config

# Функция получения предыдущего состояния
def get_previous_state(current_state):
    config = get_state_config(current_state)
    if config and "back_state" in config:
        return config["back_state"]
    return None