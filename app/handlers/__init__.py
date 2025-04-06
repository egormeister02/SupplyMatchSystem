"""
Handlers initialization
"""

from app.handlers import user, base, actions, suppliers

def register_all_handlers(dp):
    """Register all available handlers"""
    base.register_handlers(dp)
    actions.register_handlers(dp)
    user.register_handlers(dp)
    suppliers.register_handlers(dp)
