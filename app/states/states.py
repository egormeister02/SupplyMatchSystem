from aiogram.fsm.state import StatesGroup, State

class RegistrationStates(StatesGroup):
    """States for user registration process"""
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_email = State()  # Email address
    waiting_contact = State()  # Optional phone number
    confirm_registration = State()

