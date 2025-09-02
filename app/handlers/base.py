from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router(name="base_commands")

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Бот готов к разработке. 🚀")

def register_handlers(dp):
    dp.include_router(router)