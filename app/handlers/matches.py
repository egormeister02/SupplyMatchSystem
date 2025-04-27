"""
Обработчики для взаимодействия поставщиков с заявками через matches
"""

import logging
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.services.database import DBService, get_db_session
from app.utils.message_utils import send_request_card

logger = logging.getLogger(__name__)

router = Router()

# Обработчик нажатия кнопки "Принять заявку"
@router.callback_query(F.data.startswith("match:accept:"))
async def accept_match(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик принятия заявки поставщиком"""
    match_id = callback.data.split(":")[2]
    
    if not match_id or not match_id.isdigit():
        await callback.answer("Некорректный идентификатор заявки", show_alert=True)
        return
    
    await callback.answer("Обрабатываем ваш запрос...")
    
    match_id = int(match_id)
    user_id = callback.from_user.id
    
    try:
        async with get_db_session() as session:
            db = DBService(session)
            
            # Сначала получаем список поставщиков, созданных этим пользователем
            supplier_query = """
                SELECT id FROM suppliers WHERE created_by_id = :user_id
            """
            suppliers = await db.fetch_all(supplier_query, {"user_id": user_id})
            
            if not suppliers:
                await callback.message.answer("У вас нет зарегистрированных поставщиков в системе")
                return
                
            # Создаем список ID поставщиков пользователя
            supplier_ids = [s["id"] for s in suppliers]
            supplier_ids_str = ", ".join(str(s_id) for s_id in supplier_ids)
            
            logger.info(f"ID поставщиков пользователя {user_id}: {supplier_ids}")
            logger.info(f"Проверяем match_id={match_id} для поставщиков: {supplier_ids_str}")
            
            # Проверяем, что match существует и связан с одним из поставщиков пользователя
            check_query = f"""
                SELECT 
                    m.id,
                    m.request_id,
                    m.supplier_id,
                    m.status,
                    r.description,
                    r.contact_username,
                    r.contact_phone,
                    r.contact_email,
                    r.created_by_id as request_created_by_id
                FROM 
                    matches m
                JOIN 
                    requests r ON m.request_id = r.id
                WHERE 
                    m.id = :match_id AND m.supplier_id IN ({supplier_ids_str})
            """
            
            logger.info(f"Выполняем запрос: {check_query} с параметрами: match_id={match_id}")
            match_data = await db.fetch_one(check_query, {"match_id": match_id})
            logger.info(f"Результат запроса: {match_data}")
            
            if not match_data:
                await callback.message.answer("Ошибка: не найдена запись заявки или у вас нет прав на это действие")
                return
            
            if match_data["status"] != "pending":
                status_text = "принята" if match_data["status"] == "accepted" else "отклонена"
                await callback.message.answer(f"Эта заявка уже была {status_text} вами ранее")
                return
            
            # Обновляем статус match на "accepted"
            update_query = """
                UPDATE matches
                SET status = 'accepted'
                WHERE id = :match_id
            """
            
            await db.execute_query(update_query, {"match_id": match_id})
            await db.commit()
            
            logger.info(f"Поставщик пользователя {user_id} принял заявку (match_id={match_id})")
            
            # Обновляем сообщение поставщика
            try:
                # Обновляем клавиатуру - удаляем кнопки и добавляем информацию о клиенте
                contacts = []
                if match_data.get("contact_username"):
                    contacts.append(f"• Telegram: {match_data['contact_username']}")
                if match_data.get("contact_phone"):
                    contacts.append(f"• Телефон: {match_data['contact_phone']}")
                if match_data.get("contact_email"):
                    contacts.append(f"• Email: {match_data['contact_email']}")
                
                contact_text = "\n".join(contacts) if contacts else "Контактная информация не указана"
                
                new_text = (
                    callback.message.text +
                    f"\n\n✅ <b>Вы приняли эту заявку</b>\n\n"
                    f"<b>Контактная информация клиента:</b>\n{contact_text}"
                )
                
                # Проверяем, имеет ли сообщение фотографии
                has_photo = hasattr(callback.message, 'photo') and callback.message.photo
                has_caption = hasattr(callback.message, 'caption') and callback.message.caption is not None
                
                if has_photo and has_caption:
                    # Для сообщения с фото редактируем подпись
                    await callback.message.edit_caption(
                        caption=f"{callback.message.caption}\n\n✅ <b>Вы приняли эту заявку</b>\n\n"
                               f"<b>Контактная информация клиента:</b>\n{contact_text}",
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                elif not has_photo:
                    # Для текстового сообщения редактируем текст
                    await callback.message.edit_text(
                        text=new_text,
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                else:
                    # Если сообщение с фото но без подписи или другой тип сообщения,
                    # отправляем новое сообщение
                    raise Exception("Невозможно отредактировать сообщение, отправляем новое")
                    
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения поставщика: {e}")
                # Отправляем новое сообщение, если не удалось обновить
                await callback.message.answer(
                    f"✅ <b>Вы приняли заявку!</b>\n\n"
                    f"<b>Контактная информация клиента:</b>\n{contact_text}",
                    parse_mode="HTML"
                )
    
    except Exception as e:
        logger.error(f"Ошибка при принятии заявки (match_id={match_id}): {e}")
        await callback.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")

# Обработчик нажатия кнопки "Отклонить"
@router.callback_query(F.data.startswith("match:reject:"))
async def reject_match(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик отклонения заявки поставщиком"""
    match_id = callback.data.split(":")[2]
    
    if not match_id or not match_id.isdigit():
        await callback.answer("Некорректный идентификатор заявки", show_alert=True)
        return
    
    await callback.answer("Заявка отклонена")
    
    match_id = int(match_id)
    user_id = callback.from_user.id
    
    try:
        async with get_db_session() as session:
            db = DBService(session)
            
            # Сначала получаем список поставщиков, созданных этим пользователем
            supplier_query = """
                SELECT id FROM suppliers WHERE created_by_id = :user_id
            """
            suppliers = await db.fetch_all(supplier_query, {"user_id": user_id})
            
            if not suppliers:
                await callback.message.answer("У вас нет зарегистрированных поставщиков в системе")
                return
                
            # Создаем список ID поставщиков пользователя
            supplier_ids = [s["id"] for s in suppliers]
            supplier_ids_str = ", ".join(str(s_id) for s_id in supplier_ids)
            
            logger.info(f"ID поставщиков пользователя {user_id}: {supplier_ids}")
            logger.info(f"Проверяем match_id={match_id} для поставщиков: {supplier_ids_str}")
            
            # Проверяем, что match существует и связан с одним из поставщиков пользователя
            check_query = f"""
                SELECT 
                    m.id,
                    m.status
                FROM 
                    matches m
                WHERE 
                    m.id = :match_id AND m.supplier_id IN ({supplier_ids_str})
            """
            
            logger.info(f"Выполняем запрос: {check_query} с параметрами: match_id={match_id}")
            match_data = await db.fetch_one(check_query, {"match_id": match_id})
            logger.info(f"Результат запроса: {match_data}")
            
            if not match_data:
                await callback.message.answer("Ошибка: не найдена запись заявки или у вас нет прав на это действие")
                return
            
            if match_data["status"] != "pending":
                status_text = "принята" if match_data["status"] == "accepted" else "отклонена"
                await callback.message.answer(f"Эта заявка уже была {status_text} вами ранее")
                return
            
            # Обновляем статус match на "rejected"
            update_query = """
                UPDATE matches
                SET status = 'rejected'
                WHERE id = :match_id
            """
            
            await db.execute_query(update_query, {"match_id": match_id})
            await db.commit()
            
            logger.info(f"Поставщик пользователя {user_id} отклонил заявку (match_id={match_id})")
            
            # Обновляем сообщение поставщика
            try:
                # Проверяем, имеет ли сообщение фотографии
                has_photo = hasattr(callback.message, 'photo') and callback.message.photo
                has_caption = hasattr(callback.message, 'caption') and callback.message.caption is not None
                
                if has_photo and has_caption:
                    # Для сообщения с фото редактируем подпись
                    await callback.message.edit_caption(
                        caption=f"{callback.message.caption}\n\n❌ Вы отклонили эту заявку",
                        reply_markup=None
                    )
                elif not has_photo:
                    # Для текстового сообщения редактируем текст
                    await callback.message.edit_text(
                        text=f"{callback.message.text}\n\n❌ Вы отклонили эту заявку",
                        reply_markup=None
                    )
                else:
                    # Если сообщение с фото но без подписи или другой тип сообщения,
                    # отправляем новое сообщение
                    raise Exception("Невозможно отредактировать сообщение, отправляем новое")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения поставщика: {e}")
                await callback.message.answer("✅ Заявка успешно отклонена")
    
    except Exception as e:
        logger.error(f"Ошибка при отклонении заявки (match_id={match_id}): {e}")
        await callback.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")

# Обработчик нажатия кнопки "Подробности"
@router.callback_query(F.data.startswith("match:details:"))
async def show_match_details(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик запроса подробностей о заявке"""
    match_id = callback.data.split(":")[2]
    
    if not match_id or not match_id.isdigit():
        await callback.answer("Некорректный идентификатор заявки", show_alert=True)
        return
    
    await callback.answer()
    
    match_id = int(match_id)
    user_id = callback.from_user.id
    
    try:
        # Получаем данные о заявке
        async with get_db_session() as session:
            db = DBService(session)
            
            # Сначала получаем список поставщиков, созданных этим пользователем
            supplier_query = """
                SELECT id FROM suppliers WHERE created_by_id = :user_id
            """
            suppliers = await db.fetch_all(supplier_query, {"user_id": user_id})
            
            if not suppliers:
                await callback.message.answer("У вас нет зарегистрированных поставщиков в системе")
                return
                
            # Создаем список ID поставщиков пользователя
            supplier_ids = [s["id"] for s in suppliers]
            supplier_ids_str = ", ".join(str(s_id) for s_id in supplier_ids)
            
            logger.info(f"ID поставщиков пользователя {user_id}: {supplier_ids}")
            logger.info(f"Проверяем match_id={match_id} для поставщиков: {supplier_ids_str}")
            
            # Проверяем, что match существует и связан с одним из поставщиков пользователя
            check_query = f"""
                SELECT 
                    m.id,
                    m.request_id,
                    m.supplier_id,
                    m.status
                FROM 
                    matches m
                WHERE 
                    m.id = :match_id AND m.supplier_id IN ({supplier_ids_str})
            """
            
            logger.info(f"Выполняем запрос: {check_query} с параметрами: match_id={match_id}")
            match_data = await db.fetch_one(check_query, {"match_id": match_id})
            logger.info(f"Результат запроса: {match_data}")
            
            if not match_data:
                await callback.message.answer("Ошибка: не найдена запись заявки или у вас нет прав на это действие")
                return
            
            # Получаем полные данные о заявке
            request_id = match_data["request_id"]
            request_data = await DBService.get_request_by_id_static(request_id)
            
            if not request_data:
                await callback.message.answer("Ошибка: не удалось получить данные заявки")
                return
            
            # Формируем клавиатуру с кнопками действий
            # Если заявка еще не обработана, показываем кнопки принять/отклонить
            # Иначе показываем только кнопку назад
            keyboard = None
            
            if match_data["status"] == "pending":
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Принять заявку",
                                callback_data=f"match:accept:{match_id}"
                            ),
                            InlineKeyboardButton(
                                text="❌ Отклонить",
                                callback_data=f"match:reject:{match_id}"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="⬅️ Назад",
                                callback_data=f"match:back:{match_id}"
                            )
                        ]
                    ]
                )
            else:
                # Для уже обработанных заявок показываем только кнопку "Назад"
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="⬅️ Назад",
                                callback_data=f"match:back:{match_id}"
                            )
                        ]
                    ]
                )
            
            # Отправляем карточку заявки с использованием готовой функции
            await send_request_card(
                bot=bot,
                chat_id=callback.message.chat.id,
                request=request_data,
                keyboard=keyboard,
                include_video=True,  # Включаем видео
                show_status=True     # Показываем статус заявки
            )
    
    except Exception as e:
        logger.error(f"Ошибка при получении подробностей заявки (match_id={match_id}): {e}")
        await callback.message.answer("Произошла ошибка при получении информации о заявке. Пожалуйста, попробуйте позже.")

# Обработчик нажатия кнопки "Назад" в подробной информации
@router.callback_query(F.data.startswith("match:back:"))
async def go_back_from_details(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки Назад из подробной информации о заявке"""
    await callback.answer()
    
    # Просто удаляем сообщение с подробностями
    await callback.message.delete()
    
    logger.info(f"Пользователь {callback.from_user.id} вернулся из просмотра подробностей заявки") 

def register_handlers(dp):
    dp.include_router(router)