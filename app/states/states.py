from aiogram.fsm.state import StatesGroup, State

class RegistrationStates(StatesGroup):
    """States for user registration process"""
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_email = State()  # Email address
    waiting_contact = State()  # Optional phone number
    confirm_registration = State()

class SupplierCreationStates(StatesGroup):
    """States for supplier creation process"""
    waiting_company_name = State()
    waiting_product_name = State()
    waiting_main_category = State()
    waiting_subcategory = State()
    confirm_supplier_creation = State()

