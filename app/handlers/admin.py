"""
Обработчики для взаимодействия с администраторами
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command as CommandFilter
from app.utils.message_utils import send_request_card, remove_keyboard_from_context

from app.services import get_db_session, DBService, admin_chat_service
from app.utils.message_utils import send_supplier_card
from app.config import config
from app.services.notification_queue import notification_queue_service

# Инициализируем роутер
router = Router()
logger = logging.getLogger(__name__)

# Состояния для работы с админскими действиями
class AdminStates(StatesGroup):
    waiting_rejection_reason = State()  # Ожидание причины отклонения поставщика
    waiting_request_rejection_reason = State()  # Ожидание причины отклонения заявки

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
            
        # Сохраняем данные поставщика в состоянии
        await state.update_data(supplier_data=supplier_data)
        
        # Обновляем поле verified_by_id в базе данных
        try:
            async with get_db_session() as session:
                db_service = DBService(session)
                update_query = """
                    UPDATE suppliers 
                    SET verified_by_id = :admin_id 
                    WHERE id = :supplier_id
                """
                # Преобразуем supplier_id в целое число
                supplier_id_int = int(supplier_id)
                await db_service.execute_query(update_query, {"admin_id": admin_id, "supplier_id": supplier_id_int})
                await db_service.commit()
                logger.info(f"Поставщик {supplier_id} назначен администратору {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении поля verified_by_id: {e}")
            # Продолжаем выполнение даже в случае ошибки
        
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
                keyboard=inline_keyboard,
                include_video=True  # Включаем видео в группу при просмотре всех фото
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
        # Получаем данные поставщика из состояния
        state_data = await state.get_data()
        supplier_data = state_data.get("supplier_data")
        
        # Если данных нет в состоянии, запрашиваем из базы данных
        if not supplier_data:
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
    supplier_data = state_data.get("supplier_data")
    
    try:
        # Если данных нет в состоянии, запрашиваем из базы данных
        if not supplier_data:
            supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
            if not supplier_data:
                await message.answer(f"Ошибка: поставщик с ID {supplier_id} не найден")
                await state.clear()
                return
        
        # Обновляем статус поставщика и сохраняем причину отклонения
        await DBService.update_supplier_status(int(supplier_id), "rejected", rejection_reason=reason)
        
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
    
    try:
        # Получаем текущие данные из состояния
        current_state_data = await state.get_data()
        
        # Проверяем, есть ли уже данные поставщика в состоянии
        if current_state_data.get("supplier_id") == supplier_id and current_state_data.get("is_admin_edit"):
            # Используем имеющиеся данные без запроса к базе данных
            logger.info(f"Продолжаем редактирование поставщика {supplier_id} с данными из состояния")
            supplier_data = current_state_data.get("supplier_data")
        else:
            # Проверяем, есть ли данные поставщика в состоянии
            supplier_data = current_state_data.get("supplier_data")
            
            # Если нет, получаем данные о поставщике из базы данных
            if not supplier_data:
                supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
                if not supplier_data:
                    await callback.message.answer(f"Ошибка: поставщик с ID {supplier_id} не найден")
                    return
            
            # Сохраняем данные поставщика в состояние
            await state.update_data({
                "supplier_id": supplier_id,
                "supplier_data": supplier_data,
                "company_name": supplier_data.get("company_name", ""),
                "product_name": supplier_data.get("product_name", ""),
                "main_category": supplier_data.get("category_name", ""),
                "subcategory_name": supplier_data.get("subcategory_name", ""),
                "category_id": supplier_data.get("category_id", ""),
                "description": supplier_data.get("description", ""),
                "country": supplier_data.get("country", ""),
                "region": supplier_data.get("region", ""),
                "city": supplier_data.get("city", ""),
                "address": supplier_data.get("address", ""),
                "contact_username": supplier_data.get("contact_username", ""),
                "contact_phone": supplier_data.get("contact_phone", ""),
                "contact_email": supplier_data.get("contact_email", ""),
                "photos": supplier_data.get("photos", []),
                "video": supplier_data.get("video"),
                "user_id": supplier_data.get("created_by_id"),
                "is_admin_edit": True  # Флаг, что редактирование выполняет админ
            })
        
        # Получаем конфигурацию для выбора атрибута
        from app.states.state_config import get_state_config
        from app.states.states import SupplierCreationStates
        
        edit_config = get_state_config(SupplierCreationStates.select_attribute_to_edit)
        attributes = edit_config.get("attributes", [])
        
        # Формируем нумерованный список атрибутов
        attributes_text = "Выберите, что вы хотите отредактировать (введите номер):\n\n"
        for idx, attr in enumerate(attributes, 1):
            attributes_text += f"{idx}. {attr['display']}\n"
        
        # Устанавливаем состояние выбора атрибута
        await state.set_state(SupplierCreationStates.select_attribute_to_edit)
        
        # Сохраняем список атрибутов в состоянии
        await state.update_data(edit_attributes=attributes)
        
        # Отправляем сообщение с выбором атрибутов и добавляем кнопку для возврата
        await callback.message.answer(
            attributes_text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Отменить редактирование",
                        callback_data=admin_chat_service.create_admin_callback_data("cancel_edit", supplier_id=supplier_id)
                    )]
                ]
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка при подготовке к редактированию поставщика {supplier_id}: {e}")
        await callback.message.answer(f"Произошла ошибка при подготовке к редактированию: {str(e)}")

# Обработчик для отмены редактирования
@router.callback_query(F.data.startswith("admin:cancel_edit"))
async def cancel_edit_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Отменяет редактирование поставщика администратором
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    is_confirm_cancel = data.get("confirm") == "yes"
    
    if not is_confirm_cancel:
        # Спрашиваем пользователя, уверен ли он, что хочет отменить редактирование
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Сохранить изменения и выйти", 
                        callback_data=admin_chat_service.create_admin_callback_data(
                            "save_supplier", 
                            supplier_id=supplier_id
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Выйти без сохранения", 
                        callback_data=admin_chat_service.create_admin_callback_data(
                            "cancel_edit", 
                            supplier_id=supplier_id,
                            confirm="yes"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Вернуться к редактированию", 
                        callback_data=admin_chat_service.create_admin_callback_data(
                            "edit_supplier", 
                            supplier_id=supplier_id
                        )
                    )
                ]
            ]
        )
        
        await callback.message.answer(
            "⚠️ У вас есть несохраненные изменения. Что вы хотите сделать?",
            reply_markup=keyboard
        )
        return
    
    # Если пользователь подтвердил отмену
    # Очищаем состояние
    await state.clear()
    
    # Информируем админа об отмене
    await callback.message.answer("Редактирование поставщика отменено без сохранения изменений.")
    
    # Заново отправляем карточку поставщика с кнопками действий
    if supplier_id:
        try:
            # Получаем данные поставщика из состояния
            state_data = await state.get_data()
            supplier_data = state_data.get("supplier_data")
            
            # Если данных нет в состоянии, запрашиваем из базы данных
            if not supplier_data:
                supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
                
            if supplier_data:
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
                
                # Обновляем данные в состоянии
                await state.update_data(supplier_data=supplier_data)
                
                # Отправляем карточку с использованием общей функции
                from app.utils.message_utils import send_supplier_card
                await send_supplier_card(
                    bot=bot,
                    chat_id=callback.from_user.id,
                    supplier=supplier_data,
                    keyboard=inline_keyboard,
                    include_video=True  # Включаем видео в группу при просмотре всех фото
                )
        except Exception as e:
            logger.error(f"Ошибка при повторной отправке карточки поставщика: {e}")
            await callback.message.answer("Не удалось загрузить актуальную информацию о поставщике.")

# Обработчик для сохранения отредактированных данных поставщика
@router.callback_query(F.data.startswith("admin:save_supplier"))
async def save_edited_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Сохраняет отредактированные данные поставщика
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    supplier_id = data.get("supplier_id")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: ID поставщика не указан")
        await state.clear()
        return
    
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        logger.info(f"Сохраняем отредактированные данные поставщика {supplier_id}")
        logger.info(f"Данные для сохранения: {state_data}")
        
        async with get_db_session() as session:
            db_service = DBService(session)
            
            # Обновляем данные поставщика
            success = await db_service.update_supplier(
                supplier_id=int(supplier_id),
                company_name=state_data.get("company_name"),
                product_name=state_data.get("product_name"),
                category_id=state_data.get("category_id"),
                description=state_data.get("description"),
                country=state_data.get("country"),
                region=state_data.get("region"),
                city=state_data.get("city"),
                address=state_data.get("address"),
                contact_username=state_data.get("contact_username"),
                contact_phone=state_data.get("contact_phone"),
                contact_email=state_data.get("contact_email"),
                photos=state_data.get("photos", []),
                video=state_data.get("video")
            )
            
            if success:
                logger.info(f"Поставщик {supplier_id} успешно обновлен")
                # Очищаем состояние
                await state.clear()
                
                # Информируем админа об успешном обновлении
                await callback.message.answer("✅ Данные поставщика успешно обновлены!")
                
                # Получаем обновленные данные поставщика
                supplier_data = await DBService.get_supplier_by_id_static(int(supplier_id))
                
                # Обновляем данные в состоянии
                await state.update_data(supplier_data=supplier_data)
                
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
                                text="✏️ Редактировать снова",
                                callback_data=admin_chat_service.create_admin_callback_data(
                                    "edit_supplier", 
                                    supplier_id=supplier_id
                                )
                            )
                        ]
                    ]
                )
                
                # Отправляем обновленную карточку
                from app.utils.message_utils import send_supplier_card
                await send_supplier_card(
                    bot=bot,
                    chat_id=callback.from_user.id,
                    supplier=supplier_data,
                    keyboard=inline_keyboard,
                    include_video=True  # Включаем видео в группу при просмотре всех фото
                )
            else:
                logger.error(f"Не удалось обновить данные поставщика {supplier_id}")
                await callback.message.answer("❌ Не удалось обновить данные поставщика")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении отредактированных данных поставщика {supplier_id}: {e}")
        import traceback
        logger.error(f"Стек вызовов: {traceback.format_exc()}")
        await callback.message.answer(f"Произошла ошибка при сохранении данных: {str(e)}")
        await state.clear()

# Обработчик для показа подтверждения редактирования поставщика администратором
async def show_admin_supplier_confirmation(message: Message, state: FSMContext, bot: Bot):
    """
    Показывает информацию для подтверждения изменений поставщика администратором
    """
    # Получаем данные из состояния
    state_data = await state.get_data()
    supplier_id = state_data.get("supplier_id")
    
    if not supplier_id:
        await message.answer("Ошибка: ID поставщика не указан")
        await state.clear()
        return
    
    # Создаем текст подтверждения
    confirmation_text = "Пожалуйста, проверьте отредактированные данные о поставщике:\n\n"
    confirmation_text += f"Компания: {state_data.get('company_name', '')}\n"
    confirmation_text += f"Категория: {state_data.get('main_category', '')}\n"
    confirmation_text += f"Подкатегория: {state_data.get('subcategory_name', '')}\n"
    confirmation_text += f"Продукт/услуга: {state_data.get('product_name', '')}\n"
    confirmation_text += f"Описание: {state_data.get('description', '')}\n"
    
    # Добавляем информацию о местоположении, если она есть
    if state_data.get('country'):
        confirmation_text += f"Страна: {state_data.get('country')}\n"
        if state_data.get('region'):
            confirmation_text += f"Регион: {state_data.get('region')}\n"
        if state_data.get('city'):
            confirmation_text += f"Город: {state_data.get('city')}\n"
        if state_data.get('address'):
            confirmation_text += f"Адрес: {state_data.get('address')}\n"
    
    # Добавляем информацию о контактах
    confirmation_text += "\nКонтактная информация:\n"
    confirmation_text += f"Telegram: {state_data.get('contact_username', 'Не указан')}\n"
    confirmation_text += f"Телефон: {state_data.get('contact_phone', 'Не указан')}\n"
    confirmation_text += f"Email: {state_data.get('contact_email', 'Не указан')}\n"
    
    # Добавляем информацию о медиафайлах
    confirmation_text += "\nМедиафайлы:\n"
    photos = state_data.get('photos', [])
    if photos and len(photos) > 0:
        confirmation_text += f"- Фотографии: загружено {len(photos)} шт.\n"
    else:
        confirmation_text += "- Фотографии: не загружены\n"
    
    confirmation_text += "- Видео: загружено\n" if state_data.get('video') else "- Видео: не загружено\n"
    
    # Создаем кнопки для подтверждения или продолжения редактирования
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сохранить изменения", 
                    callback_data=admin_chat_service.create_admin_callback_data(
                        "save_supplier", 
                        supplier_id=supplier_id
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="Продолжить редактирование", 
                    callback_data=admin_chat_service.create_admin_callback_data(
                        "edit_supplier", 
                        supplier_id=supplier_id
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить изменения", 
                    callback_data=admin_chat_service.create_admin_callback_data(
                        "cancel_edit", 
                        supplier_id=supplier_id
                    )
                )
            ]
        ]
    )
    
    # Отправляем сообщение с подтверждением
    await message.answer(
        confirmation_text,
        reply_markup=keyboard
    )

# Вспомогательная функция для проверки режима редактирования админа
async def check_if_admin_editing(message: Message, state: FSMContext, attribute_name: str, bot: Bot):
    """
    Проверяет, находимся ли мы в режиме редактирования атрибута администратором
    
    Args:
        message: Объект сообщения
        state: Контекст состояния
        attribute_name: Имя редактируемого атрибута
        bot: Объект бота для вызова show_admin_supplier_confirmation
        
    Returns:
        bool: True если мы в режиме редактирования администратором и нужно вернуться к подтверждению
    """
    state_data = await state.get_data()
    if state_data.get("editing_attribute") == attribute_name and state_data.get("is_admin_edit"):
        # Сообщаем об обновлении и возвращаемся к подтверждению
        await message.answer(f"{attribute_name.replace('_', ' ').capitalize()} обновлен(а).")
        
        # Удаляем флаг редактирования, чтобы избежать зацикливания
        await state.update_data(editing_attribute=None)
        
        await show_admin_supplier_confirmation(message, state, bot)
        return True
    return False

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

# Обработчик для кнопки "Забрать себе" в общем чате администраторов для заявки
@router.callback_query(F.data.startswith("admin:take_request"), admin_chat_filter)
async def take_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает нажатие на кнопку "Забрать себе" в чате администраторов для заявки
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    request_id = data.get("request_id")
    
    if not request_id:
        await callback.message.answer("Ошибка: ID заявки не указан")
        return
    
    # Получаем данные об админе
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username or f"ID:{admin_id}"
    
    try:
        # Получаем данные о заявке
        request_data = await DBService.get_request_by_id_static(int(request_id))
        if not request_data:
            await callback.message.answer(f"Ошибка: заявка с ID {request_id} не найдена")
            return
            
        # Сохраняем данные заявки в состоянии
        await state.update_data(request_data=request_data)
        
        # Проверка и корректировка структуры фотографий
        photos = request_data.get("photos", [])
        fixed_photos = []
        
        logger.info(f"Подготовка фотографий для отправки админу {admin_id}, исходное количество: {len(photos)}")
        
        for i, photo in enumerate(photos):
            if isinstance(photo, dict):
                # Создаем новую копию фото для безопасной модификации
                fixed_photo = photo.copy()
                
                # Убеждаемся, что file_path существует
                if 'file_path' not in fixed_photo and 'storage_path' in fixed_photo:
                    fixed_photo['file_path'] = fixed_photo['storage_path']
                    logger.info(f"Фото {i+1}: добавлено поле file_path из storage_path")
                elif 'file_path' not in fixed_photo:
                    logger.warning(f"Фото {i+1} не содержит ни file_path, ни storage_path: {photo}")
                    continue
                
                fixed_photos.append(fixed_photo)
                logger.info(f"Фото {i+1} успешно подготовлено")
            else:
                logger.warning(f"Фото {i+1} имеет неверный формат: {photo}")
        
        # Заменяем список фотографий на исправленный
        request_data["photos"] = fixed_photos
        logger.info(f"Итоговое количество подготовленных фотографий: {len(fixed_photos)}")
        
        # Обновляем поле verified_by_id в базе данных
        try:
            async with get_db_session() as session:
                db_service = DBService(session)
                update_query = """
                    UPDATE requests 
                    SET verified_by_id = :admin_id 
                    WHERE id = :request_id
                """
                # Преобразуем request_id в целое число
                request_id_int = int(request_id)
                await db_service.execute_query(update_query, {"admin_id": admin_id, "request_id": request_id_int})
                await db_service.commit()
                logger.info(f"Заявка {request_id} назначена администратору {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении поля verified_by_id: {e}")
            # Продолжаем выполнение даже в случае ошибки
        
        # Проверяем тип сообщения - имеет ли оно caption (фото, видео и т.д.) или только текст
        if hasattr(callback.message, 'caption') and callback.message.caption is not None:
            # Редактируем caption для медиа-сообщений
            try:
                await callback.message.edit_caption(
                    caption=(callback.message.caption or "") + f"\n\n🔄 Заявка назначена администратору @{admin_username}",
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать подпись: {e}")
                # Если не удалось отредактировать, просто отправляем новое сообщение
                await callback.message.answer(f"🔄 Заявка назначена администратору @{admin_username}")
        else:
            # Для текстовых сообщений редактируем текст
            try:
                await callback.message.edit_text(
                    text=callback.message.text + f"\n\n🔄 Заявка назначена администратору @{admin_username}",
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать текст: {e}")
                # Если не удалось отредактировать, просто отправляем новое сообщение
                await callback.message.answer(f"🔄 Заявка назначена администратору @{admin_username}")
        
        try:
            # Создаем inline клавиатуру для действий
            inline_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=admin_chat_service.create_admin_callback_data(
                                "approve_request", 
                                request_id=request_id
                            )
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=admin_chat_service.create_admin_callback_data(
                                "reject_request", 
                                request_id=request_id
                            )
                        )
                    ]
                ]
            )
            
            # Отправляем карточку с использованием функции send_request_card
            logger.info(f"Отправляем карточку заявки {request_id} админу {admin_id} со всеми фотографиями")
            logger.info(f"Количество фотографий в запросе: {len(request_data.get('photos', []))}")
            for i, photo in enumerate(request_data.get('photos', [])):
                logger.info(f"Фото {i+1}: {photo}")
                if 'file_path' not in photo:
                    logger.warning(f"Фото {i+1} не содержит поле file_path: {photo}")
            
            request_message = await send_request_card(
                bot=bot,
                chat_id=admin_id,
                request=request_data,
                keyboard=inline_keyboard,
                include_video=True  # Включаем видео в группу при просмотре всех фото
            )
            
            # Сохраняем ID сообщения с карточкой в состоянии для последующего редактирования
            if request_message:
                # Проверяем тип возвращаемого значения и корректно получаем ID сообщения
                if isinstance(request_message, dict):
                    # Если это словарь, получаем ID сообщения с клавиатурой
                    await state.update_data(card_message_id=request_message.get("keyboard_message_id"))
                    await state.update_data(keyboard_message_id=request_message.get("keyboard_message_id"))
                else:
                    # Если это сообщение, получаем его ID напрямую
                    await state.update_data(card_message_id=request_message.message_id)
            
            logger.info(f"Карточка заявки {request_id} отправлена администратору {admin_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке карточки заявки {request_id} админу {admin_id}: {e}")
            await callback.message.answer(
                f"Ошибка при отправке карточки заявки в личный чат администратору @{admin_username}. Назначение отменено."
            )
    
    except Exception as e:
        logger.error(f"Ошибка при назначении заявки {request_id} администратору {admin_id}: {e}")
        await callback.message.answer(f"Произошла ошибка при назначении заявки: {str(e)}")

# Обработчик для кнопки "Подтвердить" в личном чате админа для заявки
@router.callback_query(F.data.startswith("admin:approve_request"))
async def handle_approve_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик принятия заявки администратором"""
    # Извлекаем ID заявки из callback data
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    request_id = data.get("request_id")
    
    if not request_id:
        await callback.answer("Ошибка: ID заявки не найден", show_alert=True)
        return
    
    admin_id = callback.from_user.id
    
    # Сначала создаем matches для заявки
    logger.info(f"Создание matches для заявки {request_id}")
    try:
        async with get_db_session() as session:
            db_service = DBService(session)
            # Обновляем статус заявки на approved
            update_query = """
                UPDATE requests
                SET status = 'approved', verified_by_id = :admin_id
                WHERE id = :request_id
            """
            # Преобразуем request_id в целое число, если это строка
            request_id_int = int(request_id) if isinstance(request_id, str) else request_id
            
            await db_service.execute_query(update_query, {
                "request_id": request_id_int,
                "admin_id": admin_id
            })
            await db_service.commit()
            logger.info(f"Статус заявки {request_id} обновлен на approved администратором {admin_id}")
            
            # Создаем matches напрямую через instance DBService
            matches = await db_service._create_matches_for_request(request_id_int)
            supplier_count = len(matches)
            logger.info(f"Создано {supplier_count} matches для заявки {request_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса заявки {request_id}: {e}")
        await callback.answer("Произошла ошибка при обработке заявки", show_alert=True)
        return
    
    # Получаем данные о заявке из БД, если не были получены ранее
    request_data = None
    try:
        # Получаем данные о заявке
        request_data = await DBService.get_request_by_id_static(int(request_id))
        if not request_data:
            await callback.answer(f"Ошибка: заявка с ID {request_id} не найдена", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Ошибка при получении данных заявки {request_id}: {e}")
        await callback.answer("Произошла ошибка при обработке заявки", show_alert=True)
        return
        
    # Уведомляем пользователя о том, что его заявка одобрена
    user_id = request_data.get("created_by_id")
    
    if user_id:
        try:
            if supplier_count > 0:
                notification_text = (
                    f"✅ Ваша заявка #{request_id} была одобрена администратором!\n\n"
                    f"Уведомление о вашей заявке отправлено {supplier_count} поставщикам. "
                    f"Если кто-то из поставщиков заинтересуется вашей заявкой, вы получите уведомление с их контактными данными."
                )
            else:
                notification_text = (
                    f"✅ Ваша заявка #{request_id} была одобрена администратором!\n\n"
                    f"К сожалению, в нашей базе нет подходящих поставщиков в выбранной вами категории. "
                    f"Мы уведомим вас, как только подходящие поставщики появятся в системе."
                )
                
            await bot.send_message(
                chat_id=user_id,
                text=notification_text
            )
            logger.info(f"Отправлено уведомление пользователю {user_id} об одобрении заявки {request_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
    
    # Если найдены matches, отправляем уведомления поставщикам
    if supplier_count > 0:
        try:
            # Отправляем уведомления поставщикам через очередь
            await notification_queue_service.add_supplier_notifications(
                bot=bot,
                request_id=int(request_id),
                matches=matches,
                request_data=request_data
            )
            logger.info(f"Добавлены уведомления в очередь для {supplier_count} поставщиков по заявке {request_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомлений поставщикам для заявки {request_id}: {e}")
    
    # Обновляем сообщение с заявкой, чтобы показать статус approved
    try:
        state_data = await state.get_data()
        keyboard_message_id = state_data.get("keyboard_message_id")
        
        if keyboard_message_id:
            approved_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="↩️ Назад к списку заявок",
                            callback_data="admin:pending_requests:1"
                        )
                    ]
                ]
            )
            
            # Обновляем текст и клавиатуру сообщения
            await bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=keyboard_message_id,
                reply_markup=approved_keyboard
            )
            
            # Отправляем подтверждение одобрения
            await callback.message.answer(
                f"✅ Заявка #{request_id} одобрена!\n\n"
                f"Уведомления отправлены {supplier_count} поставщикам."
            )
        else:
            # Просто отправляем новое сообщение
            await callback.message.answer(
                f"✅ Заявка #{request_id} одобрена!\n\n"
                f"Уведомления отправлены {supplier_count} поставщикам."
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении сообщения с заявкой {request_id}: {e}")
        await callback.message.answer(
            f"✅ Заявка #{request_id} одобрена, но возникла ошибка при обновлении сообщения."
        )
    
    # Очищаем состояние
    await state.clear()

# Обработчик для кнопки "Отклонить" в личном чате админа для заявки
@router.callback_query(F.data.startswith("admin:reject_request"))
async def handle_reject_request_click(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает нажатие на кнопку отклонения заявки
    """
    await callback.answer()
    
    # Парсим данные из callback
    data = admin_chat_service.parse_admin_callback_data(callback.data)
    request_id = data.get("request_id")
    
    if not request_id:
        await callback.message.answer("Ошибка: ID заявки не указан")
        return
    
    # Сохраняем ID заявки в состоянии
    await state.update_data(request_id=request_id)
    
    # Запрашиваем причину отклонения с кнопкой отмены
    await callback.message.answer(
        "Пожалуйста, укажите причину отклонения заявки. Это сообщение будет отправлено создателю заявки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_rejection")]
            ]
        )
    )
    
    # Устанавливаем состояние ожидания причины отклонения
    await state.set_state(AdminStates.waiting_request_rejection_reason)

# Обработчик для отмены ввода причины отклонения
@router.callback_query(F.data == "cancel_rejection", AdminStates.waiting_request_rejection_reason)
async def cancel_rejection(callback: CallbackQuery, state: FSMContext):
    """
    Отменяет процесс отклонения заявки
    """
    await callback.answer()
    
    # Удаляем сообщение с запросом причины
    await callback.message.delete()
    
    # Очищаем состояние ожидания причины отклонения
    await state.clear()

# Обработчик для получения причины отклонения заявки
@router.message(AdminStates.waiting_request_rejection_reason)
async def process_request_rejection_reason(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает ввод причины отклонения заявки
    """
    # Получаем причину отклонения
    reason = message.text.strip()
    
    if not reason:
        await message.answer("Пожалуйста, укажите причину отклонения заявки.")
        return
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    request_id = state_data.get("request_id")
    request_data = state_data.get("request_data")
    
    try:
        # Если данных нет в состоянии, запрашиваем из базы данных
        if not request_data:
            request_data = await DBService.get_request_by_id_static(int(request_id))
            if not request_data:
                await message.answer(f"Ошибка: заявка с ID {request_id} не найдена")
                await state.clear()
                return
        
        # Обновляем статус заявки и сохраняем причину отклонения
        await DBService.update_request_status(int(request_id), "rejected", rejection_reason=reason)
        
        # Получаем пользователя, создавшего заявку
        user_id = request_data.get("created_by_id")
        
        if user_id:
            # Отправляем уведомление пользователю об отклонении
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Ваша заявка #{request_id} была отклонена администратором.\n\n"
                         f"Причина: {reason}\n\n"
                         f"Вы можете внести изменения и повторно создать заявку."
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        
        # Подтверждаем отклонение заявки
        await message.answer(
            f"✅ Заявка #{request_id} успешно отклонена!\n\n"
            f"Причина: {reason}"
        )
        
        # Обновляем сообщение с карточкой заявки, убирая клавиатуру
        try:
            # Находим сообщение с карточкой заявки
            # Предполагаем, что message_id сохранен в состоянии
            card_message_id = state_data.get("card_message_id")
            
            if card_message_id:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=card_message_id,
                        reply_markup=None
                    )
                except Exception as e:
                    logger.warning(f"Не удалось убрать клавиатуру с карточки заявки: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при обновлении карточки заявки: {e}")
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении заявки {request_id}: {e}")
        await message.answer(f"Произошла ошибка при отклонении заявки: {str(e)}")
        await state.clear()

def register_handlers(dp):
    """
    Регистрирует все обработчики модуля
    """
    dp.include_router(router)
