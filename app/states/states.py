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
    waiting_location = State()
    waiting_additional_photos = State()
    waiting_video = State()
    waiting_tg_username = State()
    waiting_phone = State()
    waiting_email = State()
    confirm_supplier_creation = State()

class SupplierSearchStates(StatesGroup):
    """Состояния для поиска поставщиков"""
    waiting_category = State()
    waiting_subcategory = State()
    viewing_suppliers = State()

