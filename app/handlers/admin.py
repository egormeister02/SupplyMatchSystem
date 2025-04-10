"""
Обработчики для взаимодействия с администраторами
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command as CommandFilter

from app.services import get_db_session, DBService, admin_chat_service
from app.utils.message_utils import send_supplier_card
from app.config import config

# Инициализируем роутер
router = Router()
logger = logging.getLogger(__name__)

# Состояния для работы с админскими действиями
class AdminStates(StatesGroup):
    waiting_rejection_reason = State()  # Ожидание причины отклонения поставщика

# Фильтр для проверки, что запрос пришел из админского чата
async def admin_chat_filter(callback: CallbackQuery) -> bool:
    """
    Проверяет, что callback запрос пришел из чата администраторов
    """
    if not config.ADMIN_GROUP_CHAT_ID:
        return False
    
    return callback.message.chat.id == config.ADMIN_GROUP_CHAT_ID

# Фильтр для проверки, что сообщение отправлено администратором
async def admin_user_filter(message_or_callback) -> bool:
    """
    Проверяет, что сообщение отправлено администратором
    """
    user_id = message_or_callback.from_user.id
    admin_ids = []
    
    # Преобразуем конфигурацию ADMIN_IDS в список int значений
    if isinstance(config.ADMIN_IDS, str) and config.ADMIN_IDS:
        admin_ids = [int(admin_id) for admin_id in config.ADMIN_IDS.split(',') if admin_id.strip()]
    elif isinstance(config.ADMIN_IDS, list):
        admin_ids = [int(admin_id) for admin_id in config.ADMIN_IDS if str(admin_id).strip()]
    
    return user_id in admin_ids

# Обработчик для кнопки "Забрать себе" в общем чате администраторов
@router.callback_query(F.data.startswith("admin:take_supplier"), admin_chat_filter)
async def take_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает нажатие на кнопку "Забрать себе" в чате администраторов
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: ID поставщика не указан")
        return
    
    # Получаем данные об админе
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username or f"ID:{admin_id}"
    
    try:
        # Получаем данные о поставщике
        supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
        if not supplier_data:
            await callback.message.answer(f"Ошибка: поставщик с ID {supplier_id} не найден")
            return
        
        # Проверяем тип сообщения - имеет ли оно caption (фото, видео и т.д.) или только текст
        if hasattr(callback.message, 'caption') and callback.message.caption is not None:
            # Редактируем caption для медиа-сообщений
            try:
                await callback.message.edit_caption(
                    caption=(callback.message.caption or "") + f"\n\n🔄 Поставщик назначен администратору @{admin_username}",
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать подпись: {e}")
                # Если не удалось отредактировать, просто отправляем новое сообщение
                await callback.message.answer(f"🔄 Поставщик назначен администратору @{admin_username}")
        else:
            # Для текстовых сообщений редактируем текст
            try:
                await callback.message.edit_text(
                    text=callback.message.text + f"\n\n🔄 Поставщик назначен администратору @{admin_username}",
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать текст: {e}")
                # Если не удалось отредактировать, просто отправляем новое сообщение
                await callback.message.answer(f"🔄 Поставщик назначен администратору @{admin_username}")
        
        try:
            # Создаем inline клавиатуру для действий
            inline_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=admin_chat_service.create_admin_callback_data(
                                "approve_supplier", 
                                supplier_id=supplier_id
                            )
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=admin_chat_service.create_admin_callback_data(
                                "reject_supplier", 
                                supplier_id=supplier_id
                            )
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="✏️ Редактировать",
                            callback_data=admin_chat_service.create_admin_callback_data(
                                "edit_supplier", 
                                supplier_id=supplier_id
                            )
                        )
                    ]
                ]
            )
            
            # Отправляем карточку с использованием общей функции send_supplier_card
            await send_supplier_card(
                bot=bot,
                chat_id=admin_id,
                supplier=supplier_data,
                keyboard=inline_keyboard
            )
            
            # Отправляем информационное сообщение
            await bot.send_message(
                chat_id=admin_id,
                text=f"Вы взяли на проверку поставщика #{supplier_id}. Используйте кнопки для выполнения действий."
            )
            
            logger.info(f"Карточка поставщика {supplier_id} отправлена администратору {admin_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке карточки поставщика {supplier_id} админу {admin_id}: {e}")
            await callback.message.answer(
                f"Ошибка при отправке карточки поставщика в личный чат администратору @{admin_username}. Назначение отменено."
            )
    
    except Exception as e:
        logger.error(f"Ошибка при назначении поставщика {supplier_id} администратору {admin_id}: {e}")
        await callback.message.answer(f"Произошла ошибка при назначении поставщика: {str(e)}")

# Обработчик для кнопки "Подтвердить" в личном чате админа
@router.callback_query(F.data.startswith("admin:approve_supplier"))
async def handle_approve_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает подтверждение поставщика администратором
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: ID поставщика не указан")
        return
    
    try:
        # Получаем данные о поставщике
        supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
        if not supplier_data:
            await callback.message.answer(f"Ошибка: поставщик с ID {supplier_id} не найден")
            return
        
        
        await DBService.update_supplier_status(int(supplier_id), "approved")
        
        # Временная заглушка - потом заменить на реальный метод
        logger.info(f"Поставщик {supplier_id} одобрен администратором {callback.from_user.id}")
        
        # Получаем пользователя, создавшего поставщика
        user_id = supplier_data.get("created_by_id")
        
        if user_id:
            # Отправляем уведомление пользователю о подтверждении
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Ваш поставщик '{supplier_data.get('company_name')}' был проверен и одобрен администратором."
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        
        # Обновляем сообщение в личном чате админа
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Отправляем уведомление админу об успешном одобрении
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=f"✅ Поставщик '{supplier_data.get('company_name')}' успешно одобрен!"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при одобрении поставщика {supplier_id}: {e}")
        await callback.message.answer(f"Произошла ошибка при одобрении поставщика: {str(e)}")

# Обработчик для кнопки "Отклонить" в личном чате админа
@router.callback_query(F.data.startswith("admin:reject_supplier"))
async def handle_reject_supplier_click(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает нажатие на кнопку отклонения поставщика
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: ID поставщика не указан")
        return
    
    # Сохраняем ID поставщика в состоянии
    await state.update_data(supplier_id=supplier_id)
    
    # Запрашиваем причину отклонения
    await callback.message.answer(
        "Пожалуйста, укажите причину отклонения поставщика. Это сообщение будет отправлено создателю поставщика:"
    )
    
    # Устанавливаем состояние ожидания причины отклонения
    await state.set_state(AdminStates.waiting_rejection_reason)

# Обработчик для получения причины отклонения
@router.message(AdminStates.waiting_rejection_reason)
async def process_rejection_reason(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает ввод причины отклонения поставщика
    """
    # Получаем причину отклонения
    reason = message.text.strip()
    
    if not reason:
        await message.answer("Пожалуйста, укажите причину отклонения поставщика.")
        return
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    supplier_id = state_data.get("supplier_id")
    
    try:
        # Получаем данные о поставщике
        supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
        if not supplier_data:
            await message.answer(f"Ошибка: поставщик с ID {supplier_id} не найден")
            await state.clear()
            return
        
        await DBService.update_supplier_status(int(supplier_id), "rejected")
        
        # Получаем пользователя, создавшего поставщика
        user_id = supplier_data.get("created_by_id")
        
        if user_id:
            # Отправляем уведомление пользователю об отклонении
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Ваш поставщик '{supplier_data.get('company_name')}' был отклонен администратором.\n\n"
                         f"Причина: {reason}\n\n"
                         f"Вы можете внести изменения и повторно создать поставщика."
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        
        # Подтверждаем отклонение поставщика
        await message.answer(
            f"✅ Поставщик '{supplier_data.get('company_name')}' успешно отклонен!\n\n"
            f"Причина: {reason}"
        )
        
        # Очищаем состояние
        await state.clear()

        
    except Exception as e:
        logger.error(f"Ошибка при отклонении поставщика {supplier_id}: {e}")
        await message.answer(f"Произошла ошибка при отклонении поставщика: {str(e)}")
        await state.clear()

# Обработчик для кнопки "Редактировать" в личном чате админа
@router.callback_query(F.data.startswith("admin:edit_supplier"))
async def handle_edit_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает запрос на редактирование поставщика администратором
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: ID поставщика не указан")
        return
    
    # Информируем админа о том, что функция редактирования в разработке
    await callback.message.answer(
        "⚠️ Функция редактирования поставщика администратором в разработке.\n\n"
        "Пожалуйста, используйте кнопки 'Подтвердить' или 'Отклонить'."
    )

# Обработчик команды для получения ID текущего чата
@router.message(CommandFilter("chatid"))
async def get_chat_id(message: Message):
    """
    Обработчик команды /chatid для получения ID текущего чата
    Может использоваться для настройки ADMIN_GROUP_CHAT_ID в конфигурации
    """
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = getattr(message.chat, 'title', 'Личный чат')
    
    logger.info(f"Запрошен ID чата: {chat_id}, тип: {chat_type}, название: {chat_title}")
    
    # Формируем текст сообщения с информацией о чате
    response_text = f"📋 <b>Информация о текущем чате</b>\n\n"
    response_text += f"🆔 ID чата: <code>{chat_id}</code>\n"
    response_text += f"📝 Тип чата: {chat_type}\n"
    response_text += f"📌 Название: {chat_title}\n\n"
    
    if chat_type != "private":
        # Если это групповой чат, добавляем инструкцию по настройке
        response_text += "Для настройки этого чата как админского, установите следующее значение в .env:\n\n"
        response_text += f"<code>ADMIN_GROUP_CHAT_ID={chat_id}</code>\n\n"
        response_text += "Или используйте команду:\n"
        response_text += f"<code>/setadminchat {chat_id}</code>"
    
    await message.answer(
        response_text,
        parse_mode="HTML"
    )

# Обработчик команды для установки текущего чата как админского
@router.message(CommandFilter("setadminchat"))
async def set_admin_chat(message: Message, bot: Bot):
    """
    Обработчик команды /setadminchat для установки текущего чата как админского
    или указанного ID чата, если он передан в параметрах
    """
    # Проверяем, является ли пользователь админом
    admin_ids = []
    if isinstance(config.ADMIN_IDS, str) and config.ADMIN_IDS:
        admin_ids = [int(admin_id) for admin_id in config.ADMIN_IDS.split(',') if admin_id.strip()]
    elif isinstance(config.ADMIN_IDS, list):
        admin_ids = [int(admin_id) for admin_id in config.ADMIN_IDS if str(admin_id).strip()]
    
    if message.from_user.id not in admin_ids and str(message.from_user.id) not in [str(admin_id) for admin_id in admin_ids]:
        logger.warning(f"Попытка установки админ-чата пользователем без прав: {message.from_user.id}")
        await message.answer("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    # Получаем аргументы команды
    args = message.text.split(maxsplit=1)
    
    if len(args) > 1:
        # Если передан ID чата, пробуем его установить
        try:
            new_chat_id = int(args[1].strip())
            if config.update_admin_chat_id(new_chat_id):
                # Обновляем ID чата в сервисе
                admin_chat_service.admin_chat_id = new_chat_id
                
                await message.answer(
                    f"✅ ID админ-чата успешно обновлен: <code>{new_chat_id}</code>",
                    parse_mode="HTML"
                )
                
                # Проверка чата - отправляем тестовое сообщение
                try:
                    test_msg = await bot.send_message(
                        chat_id=new_chat_id,
                        text=f"✅ Этот чат установлен как чат администраторов (ID: {new_chat_id})"
                    )
                    logger.info(f"Тестовое сообщение успешно отправлено в новый админ-чат {new_chat_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке тестового сообщения в чат {new_chat_id}: {e}")
                    await message.answer(
                        f"⚠️ ID чата обновлен, но бот не может отправить сообщение в этот чат.\n"
                        f"Проверьте, добавлен ли бот в указанный чат и имеет ли права на отправку сообщений."
                    )
            else:
                await message.answer("❌ Не удалось обновить ID админ-чата. Проверьте корректность введенного ID.")
        except ValueError:
            await message.answer("❌ Некорректный формат ID чата. Используйте целое число.")
    else:
        # Устанавливаем текущий чат как админский
        current_chat_id = message.chat.id
        if config.update_admin_chat_id(current_chat_id):
            # Обновляем ID чата в сервисе
            admin_chat_service.admin_chat_id = current_chat_id
            
            await message.answer(
                f"✅ Текущий чат установлен как чат администраторов (ID: <code>{current_chat_id}</code>)",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Не удалось установить текущий чат как админский.")

def register_handlers(dp):
    """
    Регистрирует все обработчики модуля
    """
    dp.include_router(router)
