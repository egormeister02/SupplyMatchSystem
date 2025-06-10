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

from app.states.states import RegistrationStates, SupplierCreationStates, SupplierSearchStates, RequestCreationStates, MySupplierStates, MyRequestStates, ReviewStates
from app.services import get_db_session, DBService
import logging
from aiogram.fsm.state import State, StatesGroup

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
    
    app_logger = logging.getLogger("app")
    app_logger.info(f"Получено {len(main_categories)} категорий из базы данных")
    
    if state:
        await state.update_data(main_categories=main_categories)
        app_logger.info("Категории сохранены в состояние")
    
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
            {"name": "main_category", "display": "Категория и подкатегория", "state": SupplierCreationStates.waiting_main_category},
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

# Конфигурация для состояний создания заявки
request_creation_config = {
    # Выбор основной категории
    RequestCreationStates.waiting_main_category: {
        "text_func": get_categories_text,
        "markup": get_back_keyboard("requests_list", is_state=False, button_text="Вернуться к списку заявок"),
        "back_state": None,
        "error_text": "Пожалуйста, введите корректный номер категории из списка.",
    },
    
    # Выбор подкатегории
    RequestCreationStates.waiting_subcategory: {
        "text_func": get_subcategories_text,
        "markup": get_back_keyboard("waiting_main_category", is_state=True, button_text="Выбрать другую категорию", state_group="RequestCreationStates"),
        "back_state": RequestCreationStates.waiting_main_category,
        "error_text": "Пожалуйста, введите корректный номер подкатегории из списка.",
    },
    
    # Ввод описания заявки
    RequestCreationStates.waiting_description: {
        "text": "Введите подробное описание вашей заявки:",
        "markup": get_back_keyboard("waiting_subcategory", is_state=True, button_text="Назад к подкатегории", state_group="RequestCreationStates"),
        "back_state": RequestCreationStates.waiting_subcategory,
    },

    # Загрузка фотографий к заявке
    RequestCreationStates.waiting_photos: {
        "text": "Загрузите фотографии к вашей заявке (максимум 3 штуки).\n"
                "Вы можете отправить несколько фото в одном сообщении или пропустить этот шаг.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_tg_username", is_state=True, button_text="Продолжить", state_group="RequestCreationStates")],
                [get_back_button("waiting_description", is_state=True, button_text="Назад к описанию", state_group="RequestCreationStates")]
            ]
        ),
        "back_state": RequestCreationStates.waiting_description,
    },
    
    # Ввод контактного Telegram username
    RequestCreationStates.waiting_tg_username: {
        "text": "Введите Telegram username для связи.\n"
               "Это может быть ваш username или другой контакт:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать мой", callback_data="use_my_username")],
                [get_back_button("waiting_phone", is_state=True, button_text="Пропустить", state_group="RequestCreationStates")],
                [get_back_button("waiting_photos", is_state=True, button_text="Назад к фото", state_group="RequestCreationStates")]
            ]
        ),
        "back_state": RequestCreationStates.waiting_photos,
    },
    
    # Ввод контактного телефона
    RequestCreationStates.waiting_phone: {
        "text": "Введите контактный телефон в международном формате.\n"
               "Вы можете поделиться своим номером, ввести его вручную или пропустить этот шаг:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать из профиля", callback_data="use_profile_phone")],
                [InlineKeyboardButton(text="Поделиться контактом", callback_data="share_contact")],
                [get_back_button("waiting_email", is_state=True, button_text="Пропустить", state_group="RequestCreationStates")],
                [get_back_button("waiting_tg_username", is_state=True, button_text="Назад к username", state_group="RequestCreationStates")]
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
        "back_state": RequestCreationStates.waiting_tg_username,
    },
    
    # Ввод контактного email
    RequestCreationStates.waiting_email: {
        "text": "Введите контактный email или выберите другой вариант:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Использовать из профиля", callback_data="use_profile_email")],
                [InlineKeyboardButton(text="Пропустить", callback_data="request_skip_email")],
                [get_back_button("waiting_phone", is_state=True, button_text="Назад к телефону", state_group="RequestCreationStates")]
            ]
        ),
        "back_state": RequestCreationStates.waiting_phone,
    },
    
    # Подтверждение создания заявки
    RequestCreationStates.confirm_request_creation: {
        "text": "Пожалуйста, проверьте данные вашей заявки:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить", callback_data="confirm_request")],
                [InlineKeyboardButton(text="Редактировать данные", callback_data="request_edit_attributes")],
                [get_back_button("waiting_email", is_state=True, button_text="Назад к email", state_group="RequestCreationStates")]
            ]
        ),
        "back_state": RequestCreationStates.waiting_email,
    },
    
    # Выбор атрибута для редактирования
    RequestCreationStates.select_attribute_to_edit: {
        "text": "Выберите, что вы хотите отредактировать (введите номер):",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад к подтверждению", callback_data="request_back_to_confirm")]
            ]
        ),
        "back_state": RequestCreationStates.confirm_request_creation,
        "attributes": [
            {"name": "main_category", "display": "Категория и подкатегория", "state": RequestCreationStates.waiting_main_category},
            {"name": "description", "display": "Описание заявки", "state": RequestCreationStates.waiting_description},
            {"name": "photos", "display": "Фотографии", "state": RequestCreationStates.waiting_photos},
            {"name": "contact_username", "display": "Telegram контакт", "state": RequestCreationStates.waiting_tg_username},
            {"name": "contact_phone", "display": "Телефон", "state": RequestCreationStates.waiting_phone},
            {"name": "contact_email", "display": "Email", "state": RequestCreationStates.waiting_email}
        ]
    }
}

# Конфигурация для состояний "Мои поставщики"
my_supplier_config = {
    # Состояние просмотра моих поставщиков
    MySupplierStates.viewing_suppliers: {
        "text": "Мои поставщики:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="◀️", callback_data="prev_my_supplier"),
                    InlineKeyboardButton(text="1/1", callback_data="current_my_supplier"),
                    InlineKeyboardButton(text="▶️", callback_data="next_my_supplier")
                ],
                [get_back_button("suppliers", is_state=False, button_text="Назад к меню поставщиков")]
            ]
        ),
    },
    
    # Состояние подтверждения удаления поставщика
    MySupplierStates.confirm_delete: {
        "text": "Вы уверены, что хотите удалить этого поставщика? Это действие невозможно отменить.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")
                ]
            ]
        ),
        "back_state": MySupplierStates.viewing_suppliers,
    },
    
    # Состояние подтверждения повторной отправки поставщика
    MySupplierStates.confirm_reapply: {
        "text": "Вы собираетесь отправить поставщика на повторную проверку. Подтверждаете?",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_reapply"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_reapply")
                ]
            ]
        ),
        "back_state": MySupplierStates.viewing_suppliers,
    },
    
    # Состояние редактирования поставщика
    MySupplierStates.editing_supplier: {
        "text": "Редактирование поставщика:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button(MySupplierStates.viewing_suppliers, button_text="Назад к просмотру")]
            ]
        ),
        "back_state": MySupplierStates.viewing_suppliers,
    },
    
    # Состояние выбора атрибута для редактирования
    MySupplierStates.selecting_attribute: {
        "text": "Выберите, что вы хотите отредактировать:",
        "attributes": [
            {"name": "company_name", "display": "Название компании"},
            {"name": "category", "display": "Категория"},
            {"name": "product_name", "display": "Название товара/услуги"},
            {"name": "description", "display": "Описание"},
            {"name": "price", "display": "Цена"},
            {"name": "min_order", "display": "Минимальный заказ"},
            {"name": "delivery_time", "display": "Срок доставки"},
            {"name": "region", "display": "Регион"},
            {"name": "photos", "display": "Фотографии"},
            {"name": "contact_username", "display": "Telegram контакт"},
            {"name": "contact_phone", "display": "Телефон"},
            {"name": "contact_email", "display": "Email"}
        ],
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button(MySupplierStates.viewing_suppliers, button_text="Отмена")]
            ]
        ),
        "back_state": MySupplierStates.viewing_suppliers,
    },
}

# Конфигурация для "Мои заявки"
my_request_config = {
    # Состояние просмотра моих заявок
    MyRequestStates.viewing_requests: {
        "text": "Мои заявки:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="◀️", callback_data="prev_my_request"),
                    InlineKeyboardButton(text="1/1", callback_data="current_my_request"),
                    InlineKeyboardButton(text="▶️", callback_data="next_my_request")
                ],
                [get_back_button("requests", is_state=False, button_text="Назад к меню заявок")]
            ]
        ),
    },
    
    # Состояние подтверждения удаления заявки
    MyRequestStates.confirm_delete: {
        "text": "Вы уверены, что хотите удалить эту заявку? Это действие невозможно отменить.",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")
                ]
            ]
        ),
        "back_state": MyRequestStates.viewing_requests,
    },
    
    # Состояние подтверждения повторной отправки заявки
    MyRequestStates.confirm_reapply: {
        "text": "Вы собираетесь отправить заявку на повторную проверку. Подтверждаете?",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_reapply"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_reapply")
                ]
            ]
        ),
        "back_state": MyRequestStates.viewing_requests,
    },
    
    # Состояние редактирования заявки
    MyRequestStates.editing_request: {
        "text": "Редактирование заявки:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button(MyRequestStates.viewing_requests, button_text="Назад к просмотру")]
            ]
        ),
        "back_state": MyRequestStates.viewing_requests,
    },
    
    # Состояние выбора атрибута для редактирования заявки
    MyRequestStates.selecting_attribute: {
        "text": "Выберите, что вы хотите отредактировать:",
        "attributes": [
            {"name": "main_category", "display": "Основная категория"},
            {"name": "subcategory", "display": "Подкатегория"},
            {"name": "description", "display": "Описание"},
            {"name": "photos", "display": "Фотографии"},
            {"name": "contact_username", "display": "Telegram контакт"},
            {"name": "contact_phone", "display": "Телефон"},
            {"name": "contact_email", "display": "Email"}
        ],
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button(MyRequestStates.viewing_requests, button_text="Отмена")]
            ]
        ),
        "back_state": MyRequestStates.viewing_requests,
    },
}


review_states_config = {
    ReviewStates.waiting_mark: {
        "text": "Поставьте оценку поставщику:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1", callback_data="review_mark:1"),
                 InlineKeyboardButton(text="2", callback_data="review_mark:2"),
                 InlineKeyboardButton(text="3", callback_data="review_mark:3"),
                 InlineKeyboardButton(text="4", callback_data="review_mark:4"),
                 InlineKeyboardButton(text="5", callback_data="review_mark:5")],
                [InlineKeyboardButton(text="Назад к поставщику", callback_data="back_to_viewing_request_suppliers")]
            ]
        ),
        "back_state": MyRequestStates.viewing_request_suppliers,
    },
    ReviewStates.waiting_text: {
        "text": "Напишите текст отзыва:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [get_back_button("waiting_mark", is_state=True, button_text="Назад к оценке", state_group="ReviewStates")]
            ]
        ),
        "back_state": ReviewStates.waiting_mark,
    },
    ReviewStates.confirm: {
        "text": "Проверьте ваш отзыв и подтвердите отправку:",
        "markup": InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отправить", callback_data="review_send")],
                [get_back_button("waiting_text", is_state=True, button_text="Назад к тексту", state_group="ReviewStates")]
            ]
        ),
        "back_state": ReviewStates.waiting_text,
    },
}

# Функция получения конфигурации для состояния
def get_state_config(state):
    """
    Получает конфигурацию для указанного состояния.
    
    Args:
        state: Объект состояния
        
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
    elif state in request_creation_config:
        config = request_creation_config[state]
    elif state in my_supplier_config:
        config = my_supplier_config[state]
    elif state in my_request_config:
        config = my_request_config[state]
    elif state in review_states_config:
        config = review_states_config[state]
    elif state in review_states_config:
        config = review_states_config[state]
        
    return config

# Функция получения предыдущего состояния
def get_previous_state(current_state):
    """
    Возвращает состояние "назад" для текущего состояния.
    
    Args:
        current_state: Текущее состояние
        
    Returns:
        Объект состояния для возврата или None
    """
    config = get_state_config(current_state)
    if config and "back_state" in config:
        return config["back_state"]
    return None

# Helper functions for formatting lists, options, etc.
def get_category_text(category_name, subcategory_name=None):
    """
    Возвращает текстовое представление категории и подкатегории.
    
    Args:
        category_name (str): Название категории
        subcategory_name (str, optional): Название подкатегории
        
    Returns:
        str: Форматированная строка
    """
    if subcategory_name:
        return f"{category_name} ➡️ {subcategory_name}"
    return category_name