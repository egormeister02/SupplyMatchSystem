"""
Конфигурация для состояний бота.
Содержит тексты сообщений и клавиатуры для каждого состояния.
"""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from app.keyboards.inline import (
    get_back_keyboard,
    get_back_button,
)

from app.states.states import RegistrationStates, SupplierCreationStates, SupplierSearchStates
from app.services import get_db_session, DBService

# Вспомогательные функции для формирования текстов
def format_numbered_list(items, start_text="", item_formatter=lambda i, idx: f"{idx}. {i}"):
    result = start_text + "\n\n" if start_text else ""
    
    for idx, item in enumerate(items, 1):
        result += f"{item_formatter(item, idx)}\n"
    
    return result

async def get_categories_text(state: FSMContext = None):
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
        "markup": get_back_keyboard("waiting_first_name", is_state=True, button_text="Изменить имя", state_group="RegistrationStates"),
        "back_state": RegistrationStates.waiting_first_name,
    },
    
    # Состояние ожидания email
    RegistrationStates.waiting_email: {
        "text": "Теперь введите ваш email:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_contact", is_state=True, button_text="Пропустить", state_group="RegistrationStates")],
                [get_back_button("waiting_last_name", is_state=True, button_text="Изменить фамилию", state_group="RegistrationStates")]
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
                [get_back_button("waiting_first_name", is_state=True, button_text="Изменить данные", state_group="RegistrationStates")],
                [get_back_button("waiting_contact", is_state=True, button_text="Назад к вводу контакта", state_group="RegistrationStates")]
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
        "back_state": None,
    },
    
    # Выбор основной категории
    SupplierCreationStates.waiting_main_category: {
        "text_func": get_categories_text,
        "markup": get_back_keyboard("waiting_company_name", is_state=True, button_text="Изменить название компании", state_group="SupplierCreationStates"),
        "back_state": SupplierCreationStates.waiting_company_name,
        "error_text": "Пожалуйста, введите корректный номер категории из списка.",
    },
    
    # Выбор подкатегории
    SupplierCreationStates.waiting_subcategory: {
        "text_func": get_subcategories_text,
        "markup": get_back_keyboard("waiting_main_category", is_state=True, button_text="Выбрать другую категорию", state_group="SupplierCreationStates"),
        "back_state": SupplierCreationStates.waiting_main_category,
        "error_text": "Пожалуйста, введите корректный номер подкатегории из списка.",
    },
    
    # Ввод названия продукта
    SupplierCreationStates.waiting_product_name: {
        "text": "Введите название вашего основного продукта или услуги:",
        "markup": get_back_keyboard("waiting_subcategory", is_state=True, button_text="Назад к подкатегории", state_group="SupplierCreationStates"),
        "back_state": SupplierCreationStates.waiting_subcategory,
    },

    # Ввод описания продукта
    SupplierCreationStates.waiting_description: {
        "text": "Введите подробное описание вашего продукта или услуги:",
        "markup": get_back_keyboard("waiting_product_name", is_state=True, button_text="Назад к названию продукта", state_group="SupplierCreationStates"),
        "back_state": SupplierCreationStates.waiting_product_name,
    },

    # Ввод страны
    SupplierCreationStates.waiting_country: {
        "text": "Введите страну местонахождения:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_description", is_state=True, button_text="Назад к описанию", state_group="SupplierCreationStates")],
                [get_back_button("waiting_additional_photos", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")]
            ]
        ),

        "back_state": SupplierCreationStates.waiting_description,
    },

    # Ввод региона
    SupplierCreationStates.waiting_region: {
        "text": "Введите регион (область, край, республику):\n\nВы можете пропустить этот шаг, нажав на соответствующую кнопку.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_additional_photos", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_country", is_state=True, button_text="Назад к вводу страны", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_country,
    },

    # Ввод города
    SupplierCreationStates.waiting_city: {
        "text": "Введите город или населенный пункт:\n\nВы можете пропустить этот шаг, нажав на соответствующую кнопку.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_additional_photos", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_region", is_state=True, button_text="Назад к вводу региона", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_region,
    },

    # Ввод адреса
    SupplierCreationStates.waiting_address: {
        "text": "Введите точный адрес (улица, дом и т.д.):\n\nВы можете пропустить этот шаг, нажав на соответствующую кнопку.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_additional_photos", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_city", is_state=True, button_text="Назад к вводу города", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_city,
    },

    # Загрузка дополнительных фото
    SupplierCreationStates.waiting_additional_photos: {
        "text": "Загрузите фотографии вашего продукта (максимум 8 штук).\n"
                "Вы можете отправить несколько фото в одном сообщении.\n"
                "После загрузки фото вы можете загрузить еще или перейти к следующему шагу:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_video", is_state=True, button_text="Продолжить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_country", is_state=True, button_text="Назад к стране", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_address,
    },

    # Загрузка видео
    SupplierCreationStates.waiting_video: {
        "text": "Вы можете загрузить видео о вашем продукте или компании.\n"
                "Нажмите 'Пропустить' чтобы перейти к следующему шагу:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_tg_username", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_additional_photos", is_state=True, button_text="Назад к фотографиям", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_additional_photos,
    },
    
    # Ввод контактного Telegram username
    SupplierCreationStates.waiting_tg_username: {
        "text": "Введите Telegram username для связи.\n"
               "Это может быть ваш username или другой контакт:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать мой", callback_data="use_my_username")],
                [get_back_button("waiting_phone", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_video", is_state=True, button_text="Назад к видео", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_video,
    },
    
    # Ввод контактного телефона
    SupplierCreationStates.waiting_phone: {
        "text": "Введите контактный телефон в международном формате.\n"
               "Вы можете поделиться своим номером, ввести его вручную или пропустить этот шаг:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать из профиля", callback_data="use_profile_phone")],
                [InlineKeyboardButton(text="Поделиться контактом", callback_data="share_contact")],
                [get_back_button("waiting_email", is_state=True, button_text="Пропустить", state_group="SupplierCreationStates")],
                [get_back_button("waiting_tg_username", is_state=True, button_text="Назад к username", state_group="SupplierCreationStates")]
            ]
        ),
        "share_contact_markup": ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Поделиться своим", request_contact=True)],
                [KeyboardButton(text="Отмена")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        ),
        "back_state": SupplierCreationStates.waiting_tg_username,
    },
    
    # Ввод контактного email
    SupplierCreationStates.waiting_email: {
        "text": "Введите контактный email или выберите другой вариант:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать из профиля", callback_data="use_profile_email")],
                [InlineKeyboardButton(text="Пропустить", callback_data="skip_email")],
                [get_back_button("waiting_phone", is_state=True, button_text="Назад к телефону", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_phone,
    },
    
    # Подтверждение создания поставщика
    SupplierCreationStates.confirm_supplier_creation: {
        "text": "Пожалуйста, проверьте введенные данные о поставщике:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить", callback_data="confirm")],
                [InlineKeyboardButton(text="Редактировать данные", callback_data="edit_attributes")],
                [get_back_button("waiting_email", is_state=True, button_text="Назад к email", state_group="SupplierCreationStates")]
            ]
        ),
        "back_state": SupplierCreationStates.waiting_email,
    },
    
    # Выбор атрибута для редактирования
    SupplierCreationStates.select_attribute_to_edit: {
        "text": "Выберите, что вы хотите отредактировать (введите номер):",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад к подтверждению", callback_data="skip_email")]
            ]
        ),
        "back_state": SupplierCreationStates.confirm_supplier_creation,
        "attributes": [
            {"name": "company_name", "display": "Название компании", "state": SupplierCreationStates.waiting_company_name},
            {"name": "main_category", "display": "Категория", "state": SupplierCreationStates.waiting_main_category},
            {"name": "product_name", "display": "Название продукта/услуги", "state": SupplierCreationStates.waiting_product_name},
            {"name": "description", "display": "Описание", "state": SupplierCreationStates.waiting_description},
            {"name": "country", "display": "Страна", "state": SupplierCreationStates.waiting_country},
            {"name": "region", "display": "Регион", "state": SupplierCreationStates.waiting_region},
            {"name": "city", "display": "Город", "state": SupplierCreationStates.waiting_city},
            {"name": "address", "display": "Адрес", "state": SupplierCreationStates.waiting_address},
            {"name": "contact_username", "display": "Telegram контакт", "state": SupplierCreationStates.waiting_tg_username},
            {"name": "contact_phone", "display": "Телефон", "state": SupplierCreationStates.waiting_phone},
            {"name": "contact_email", "display": "Email", "state": SupplierCreationStates.waiting_email}
        ]
    }
}

# Конфигурация для состояний поиска поставщиков
supplier_search_config = {
    # Состояние ожидания выбора категории
    SupplierSearchStates.waiting_category: {
        "text_func": get_categories_text,
        "markup": get_back_keyboard("suppliers", is_state=False, button_text="Назад"),
        "error_text": "Пожалуйста, введите корректный номер категории из списка.",
    },
    
    # Состояние ожидания выбора подкатегории
    SupplierSearchStates.waiting_subcategory: {
        "text_func": get_subcategories_text,
        "markup": get_back_keyboard("waiting_category", is_state=True, button_text="Назад к категориям", state_group="SupplierSearchStates"),
        "error_text": "Пожалуйста, введите корректный номер подкатегории из списка.",
    },
    
    # Состояние просмотра поставщиков
    SupplierSearchStates.viewing_suppliers: {
        "text": "Выберите действие:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="◀️", callback_data="prev_supplier"),
                    InlineKeyboardButton(text="1/1", callback_data="current_supplier"),
                    InlineKeyboardButton(text="▶️", callback_data="next_supplier")
                ],
                [get_back_button("waiting_subcategory", is_state=True, button_text="Назад к подкатегориям", state_group="SupplierSearchStates")]
            ]
        ),
    },
}

# Функция получения конфигурации для состояния
def get_state_config(state):
    """
    Получает конфигурацию для указанного состояния.
    
    Args:
        state: Объект состояния из RegistrationStates, SupplierCreationStates или SupplierSearchStates
        
    Returns:
        dict: Конфигурация для указанного состояния или None
    """
    config = None
    
    if state in registration_config:
        config = registration_config[state]
    elif state in supplier_creation_config:
        config = supplier_creation_config[state]
    elif state in supplier_search_config:
        config = supplier_search_config[state]
        
    return config

# Функция получения предыдущего состояния
def get_previous_state(current_state):
    config = get_state_config(current_state)
    if config and "back_state" in config:
        return config["back_state"]
    return None