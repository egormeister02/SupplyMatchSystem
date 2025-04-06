from app.handlers.base import register_handlers as register_base_handlers
from app.handlers.file_handler import router as file_router
from app.handlers.user import router as user_router
from app.handlers.actions import register_handlers as register_actions_handlers

def register_all_handlers(dp):
    """Registers all command and message handlers"""
    # Register base handlers
    register_base_handlers(dp)
    
    # Register user handlers (registration and authorization)
    dp.include_router(user_router)
    
    # Register file handlers
    dp.include_router(file_router)
    
    # Register action handlers (для обработки действий без состояний)
    register_actions_handlers(dp)
    
    # Здесь можно добавить регистрацию других групп обработчиков
    # register_user_handlers(dp)
    # register_admin_handlers(dp)
