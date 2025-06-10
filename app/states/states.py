from aiogram.fsm.state import StatesGroup, State

class RegistrationStates(StatesGroup):
    """States for user registration process"""
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_email = State()  # Email address
    waiting_contact = State()  # Optional phone number
    confirm_registration = State()

class SupplierCreationStates(StatesGroup):
    """Состояния при создании поставщика"""
    waiting_company_name = State()
    waiting_main_category = State()
    waiting_subcategory = State()
    waiting_product_name = State()
    waiting_description = State()
    waiting_country = State()  # Ввод страны
    waiting_region = State()   # Ввод региона
    waiting_city = State()     # Ввод города
    waiting_address = State()  # Ввод адреса
    waiting_additional_photos = State()
    waiting_video = State()
    waiting_tg_username = State()
    waiting_phone = State()
    waiting_email = State()
    select_attribute_to_edit = State()  # Выбор атрибута для редактирования
    confirm_supplier_creation = State()

class RequestCreationStates(StatesGroup):
    """Состояния при создании заявки"""
    waiting_main_category = State()
    waiting_subcategory = State()
    waiting_description = State()
    waiting_photos = State()
    waiting_tg_username = State()  # Telegram контакт
    waiting_phone = State()      # Номер телефона
    waiting_email = State()      # Email
    select_attribute_to_edit = State()  # Выбор атрибута для редактирования
    confirm_request_creation = State()

class SupplierSearchStates(StatesGroup):
    """Состояния для поиска поставщиков"""
    waiting_category = State()
    waiting_subcategory = State()
    viewing_suppliers = State()

class AdminStates(StatesGroup):
    waiting_admin_command = State()
    waiting_user_id = State()
    waiting_supplier_id = State()
    waiting_rejection_reason = State()
    waiting_admin_edit_supplier = State()
    waiting_admin_edit_attribute = State()
    waiting_admin_confirmation = State()

# Новые состояния для работы с "Мои поставщики"
class MySupplierStates(StatesGroup):
    viewing_suppliers = State()    # Просмотр поставщиков пользователя
    confirm_delete = State()       # Подтверждение удаления поставщика
    confirm_reapply = State()      # Подтверждение повторной отправки на проверку
    editing_supplier = State()     # Редактирование поставщика
    selecting_attribute = State()  # Выбор атрибута для редактирования

# Новые состояния для работы с "Мои заявки"
class MyRequestStates(StatesGroup):
    """Состояния для управления своими заявками"""
    viewing_requests = State()
    confirm_delete = State()
    confirm_reapply = State()
    viewing_request_suppliers = State()  # Состояние просмотра откликов на заявку
    editing_request = State()      # Редактирование заявки
    selecting_attribute = State()  # Выбор атрибута для редактирования

class ReviewStates(StatesGroup):
    waiting_mark = State()
    waiting_text = State()
    confirm = State()
