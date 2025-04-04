from app.handlers.base import register_handlers as register_base_handlers

def register_all_handlers(dp):
    """Регистрирует все обработчики команд и сообщений"""
    # Регистрируем базовые обработчики
    register_base_handlers(dp)
    
    # Здесь можно добавить регистрацию других групп обработчиков
    # register_user_handlers(dp)
    # register_admin_handlers(dp)
