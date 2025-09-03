from aiogram.fsm.state import StatesGroup, State


class JokeStates(StatesGroup):
    waiting_topic = State()

