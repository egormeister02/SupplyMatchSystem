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
                # Контактная информация теперь не отображается в сообщении
                # Проверяем, имеет ли сообщение фотографии
                has_photo = hasattr(callback.message, 'photo') and callback.message.photo
                has_caption = hasattr(callback.message, 'caption') and callback.message.caption is not None
                
                if has_photo and has_caption:
                    # Для сообщения с фото редактируем подпись
                    await callback.message.edit_caption(
                        caption=f"{callback.message.caption}\n\n✅ Вы откликнулись на эту заявку",
                        reply_markup=None
                    )
                elif not has_photo:
                    # Для текстового сообщения редактируем текст
                    await callback.message.edit_text(
                        text=f"{callback.message.text}\n\n✅ Вы откликнулись на эту заявку",
                        reply_markup=None
                    )
                else:
                    logger.error("Не удалось отредактировать сообщение с заявкой")
                    
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения поставщика: {e}")
    
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
                    logger.error("Не удалось отредактировать сообщение с заявкой")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения поставщика: {e}")
    
    except Exception as e:
        logger.error(f"Ошибка при отклонении заявки (match_id={match_id}): {e}")
        await callback.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")

def register_handlers(dp):
    dp.include_router(router)