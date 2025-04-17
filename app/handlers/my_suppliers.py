"""
Обработчики для управления поставщиками пользователя (раздел "Мои поставщики").
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.states.states import MySupplierStates
from app.services import get_db_session, DBService
from app.utils.message_utils import send_supplier_card
from app.config.action_config import get_action_config
from app.config.logging import app_logger
from app.keyboards.inline import get_back_button, get_back_keyboard

# Инициализируем роутер
router = Router()

# Обработчик для кнопки "Показать моих поставщиков"
@router.callback_query(F.data == "view_my_suppliers")
async def handle_view_my_suppliers(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для кнопки просмотра своих поставщиков.
    Показывает список поставщиков пользователя.
    """
    await callback.answer()
    await callback.message.delete()
    
    user_id = callback.from_user.id
    
    try:
        # Получаем список поставщиков пользователя
        suppliers = await DBService.get_user_suppliers_static(user_id)
        
        # Если поставщиков нет
        if not suppliers:
            await callback.message.answer(
                "У вас пока нет созданных поставщиков. Вы можете создать нового поставщика через меню поставщиков."
            )
            return
            
        # Сохраняем список поставщиков в состояние
        await state.update_data(
            user_suppliers=suppliers,
            current_index=0
        )
        
        # Устанавливаем состояние просмотра
        await state.set_state(MySupplierStates.viewing_suppliers)
        
        # Получаем текущий индекс и поставщика
        current_index = 0
        supplier = suppliers[current_index]
        
        # Создаем клавиатуру для навигации и управления
        keyboard = create_supplier_navigation_keyboard(supplier, current_index, len(suppliers))
        
        # Отправляем карточку поставщика
        result = await send_supplier_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            supplier=supplier,
            keyboard=keyboard,
            show_status=True  # Показываем статус поставщика
        )
        
        # Сохраняем message_id для дальнейшего использования
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
        
    except Exception as e:
        app_logger.error(f"Ошибка при получении поставщиков пользователя: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке ваших поставщиков. Пожалуйста, попробуйте позже."
        )

# Функция для создания клавиатуры навигации по поставщикам
def create_supplier_navigation_keyboard(supplier, current_index, total_count):
    """
    Создает клавиатуру для навигации и управления поставщиком.
    
    Args:
        supplier (dict): Данные поставщика
        current_index (int): Текущий индекс в списке
        total_count (int): Общее количество поставщиков
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для управления поставщиком
    """
    # Основные кнопки навигации
    navigation_row = [
        InlineKeyboardButton(text="◀️", callback_data="prev_my_supplier"),
        InlineKeyboardButton(text=f"{current_index + 1}/{total_count}", callback_data="current_my_supplier"),
        InlineKeyboardButton(text="▶️", callback_data="next_my_supplier")
    ]
    
    # Определяем дополнительные кнопки в зависимости от статуса
    status = supplier.get("status", "pending")
    supplier_id = supplier.get("id")
    
    keyboard = []
    keyboard.append(navigation_row)
    
    if status == "approved":
        # Для одобренных поставщиков - только кнопка удаления
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_supplier:{supplier_id}")
        ])
    elif status == "rejected":
        # Для отклоненных поставщиков - удаление, редактирование, повторная отправка
        keyboard.append([
            InlineKeyboardButton(text="🔄 Отправить на повторную проверку", callback_data=f"reapply_supplier:{supplier_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_supplier:{supplier_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_supplier:{supplier_id}")
        ])
    
    # Добавляем кнопку возврата к меню
    keyboard.append([
        get_back_button("suppliers", is_state=False, button_text="Назад")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчик для кнопки "Следующий поставщик"
@router.callback_query(MySupplierStates.viewing_suppliers, F.data == "next_my_supplier")
async def next_my_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к следующему поставщику в списке.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("user_suppliers", [])
    current_index = state_data.get("current_index", 0)
    
    # Рассчитываем следующий индекс (с цикличностью)
    next_index = (current_index + 1) % len(suppliers)
    
    # Получаем следующего поставщика
    supplier = suppliers[next_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=next_index)
    
    # Создаем клавиатуру
    keyboard = create_supplier_navigation_keyboard(supplier, next_index, len(suppliers))
    
    # Получаем информацию о предыдущих сообщениях
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем предыдущие сообщения, если они есть
    try:
        for msg_id in media_message_ids:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
        
        if keyboard_message_id and keyboard_message_id not in media_message_ids:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=keyboard_message_id)
    except Exception as e:
        app_logger.error(f"Ошибка при удалении предыдущих сообщений: {e}")
    
    # Отправляем новую карточку
    result = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=supplier,
        keyboard=keyboard,
        show_status=True
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для кнопки "Предыдущий поставщик"
@router.callback_query(MySupplierStates.viewing_suppliers, F.data == "prev_my_supplier")
async def prev_my_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к предыдущему поставщику в списке.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("user_suppliers", [])
    current_index = state_data.get("current_index", 0)
    
    # Рассчитываем предыдущий индекс (с цикличностью)
    prev_index = (current_index - 1) % len(suppliers)
    
    # Получаем предыдущего поставщика
    supplier = suppliers[prev_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=prev_index)
    
    # Создаем клавиатуру
    keyboard = create_supplier_navigation_keyboard(supplier, prev_index, len(suppliers))
    
    # Получаем информацию о предыдущих сообщениях
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем предыдущие сообщения, если они есть
    try:
        for msg_id in media_message_ids:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
        
        if keyboard_message_id and keyboard_message_id not in media_message_ids:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=keyboard_message_id)
    except Exception as e:
        app_logger.error(f"Ошибка при удалении предыдущих сообщений: {e}")
    
    # Отправляем новую карточку
    result = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=supplier,
        keyboard=keyboard,
        show_status=True
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для удаления поставщика (подтверждение)
@router.callback_query(MySupplierStates.viewing_suppliers, F.data.startswith("delete_supplier:"))
async def confirm_delete_supplier(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для запроса подтверждения удаления поставщика.
    """
    await callback.answer()
    
    # Получаем ID поставщика из callback_data
    supplier_id = int(callback.data.split(":")[1])
    
    # Сохраняем ID поставщика для удаления
    await state.update_data(supplier_to_delete=supplier_id)
    
    # Устанавливаем состояние подтверждения удаления
    await state.set_state(MySupplierStates.confirm_delete)
    
    # Отправляем запрос на подтверждение
    await callback.message.answer(
        "Вы уверены, что хотите удалить этого поставщика? Это действие невозможно отменить.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")
                ]
            ]
        )
    )

# Обработчик для подтверждения удаления
@router.callback_query(MySupplierStates.confirm_delete, F.data == "confirm_delete")
async def delete_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для подтверждения удаления поставщика.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    supplier_id = state_data.get("supplier_to_delete")
    
    # Получаем ID сообщений текущей карточки для удаления
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    if not supplier_id:
        await callback.message.answer("Ошибка: не найден ID поставщика для удаления")
        await state.set_state(MySupplierStates.viewing_suppliers)
        return
    
    # Удаляем сообщения текущей карточки поставщика
    try:
        for msg_id in media_message_ids:
            try:
                await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
            except Exception as e:
                app_logger.error(f"Ошибка при удалении медиа сообщения {msg_id}: {e}")
        
        if keyboard_message_id and keyboard_message_id not in media_message_ids:
            try:
                await bot.delete_message(chat_id=callback.message.chat.id, message_id=keyboard_message_id)
            except Exception as e:
                app_logger.error(f"Ошибка при удалении сообщения с клавиатурой {keyboard_message_id}: {e}")
    except Exception as e:
        app_logger.error(f"Общая ошибка при удалении сообщений карточки: {e}")
        
    # Выполняем удаление поставщика
    deleted = await DBService.delete_supplier_static(supplier_id)
    
    if deleted:
        # Получаем обновленный список поставщиков
        suppliers = await DBService.get_user_suppliers_static(callback.from_user.id)
        
        if not suppliers:
            # Если больше нет поставщиков, возвращаемся в меню
            await callback.message.answer(
                "Поставщик успешно удален. У вас больше нет созданных поставщиков."
            )
            await state.clear()
            
            # Показываем меню поставщиков
            action_config = get_action_config("my_suppliers")
            await callback.message.answer(
                action_config["text"],
                reply_markup=action_config["markup"]
            )
            return
            
        # Обновляем список поставщиков в состоянии
        current_index = 0
        await state.update_data(
            user_suppliers=suppliers,
            current_index=current_index
        )
        
        # Уведомляем об успешном удалении
        await callback.message.answer("Поставщик успешно удален!")
        
        # Отображаем следующего поставщика
        supplier = suppliers[current_index]
        keyboard = create_supplier_navigation_keyboard(supplier, current_index, len(suppliers))
        
        # Возвращаемся к состоянию просмотра поставщиков
        await state.set_state(MySupplierStates.viewing_suppliers)
        
        # Отправляем новую карточку
        result = await send_supplier_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            supplier=supplier,
            keyboard=keyboard,
            show_status=True
        )
        
        # Обновляем ID сообщений в состоянии
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
    else:
        await callback.message.answer(
            "Произошла ошибка при удалении поставщика. Пожалуйста, попробуйте позже."
        )
        # Возвращаемся к состоянию просмотра
        await state.set_state(MySupplierStates.viewing_suppliers)

# Обработчик для отмены удаления
@router.callback_query(MySupplierStates.confirm_delete, F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для отмены удаления поставщика.
    """
    await callback.answer()
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Возвращаемся к состоянию просмотра
    await state.set_state(MySupplierStates.viewing_suppliers)
    
    await callback.message.answer("Удаление отменено.")

# Обработчик для повторной отправки поставщика на проверку
@router.callback_query(MySupplierStates.viewing_suppliers, F.data.startswith("reapply_supplier:"))
async def reapply_supplier_click(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для нажатия на кнопку "Отправить на повторную проверку".
    Запрашивает подтверждение у пользователя.
    """
    await callback.answer()
    
    # Получаем ID поставщика из callback_data
    supplier_id = int(callback.data.split(":")[1])
    
    # Сохраняем ID поставщика для повторной отправки
    await state.update_data(supplier_to_reapply=supplier_id)
    
    # Получаем информацию о поставщике, чтобы показать причину отклонения
    supplier_data = await DBService.get_supplier_by_id_static(supplier_id)
    if not supplier_data:
        await callback.message.answer("Ошибка: не удалось получить информацию о поставщике")
        return
    
    # Формируем сообщение с причиной отклонения (если она есть)
    rejection_reason = supplier_data.get("rejection_reason", "Причина не указана")
    
    # Создаем сообщение для подтверждения
    confirm_text = f"Вы собираетесь отправить поставщика '{supplier_data.get('company_name')}' на повторную проверку.\n\n"
    confirm_text += f"❗️ Причина предыдущего отклонения: {rejection_reason}\n\n"
    confirm_text += "Подтверждаете отправку?"
    
    # Устанавливаем состояние подтверждения повторной отправки
    await state.set_state(MySupplierStates.confirm_reapply)
    
    # Отправляем запрос на подтверждение
    await callback.message.answer(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_reapply"),
                    InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_reapply")
                ]
            ]
        )
    )

@router.callback_query(MySupplierStates.confirm_reapply, F.data == "confirm_reapply")
async def confirm_reapply_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для подтверждения повторной отправки поставщика на проверку.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    supplier_id = state_data.get("supplier_to_reapply")
    
    # Получаем ID сообщений текущей карточки для удаления
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Удаляем сообщения карточки поставщика, так как они устарели
    try:
        for msg_id in media_message_ids:
            try:
                await bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
            except Exception as e:
                app_logger.error(f"Ошибка при удалении медиа сообщения {msg_id}: {e}")
        
        if keyboard_message_id and keyboard_message_id not in media_message_ids:
            try:
                await bot.delete_message(chat_id=callback.message.chat.id, message_id=keyboard_message_id)
            except Exception as e:
                app_logger.error(f"Ошибка при удалении сообщения с клавиатурой {keyboard_message_id}: {e}")
    except Exception as e:
        app_logger.error(f"Общая ошибка при удалении сообщений карточки: {e}")
    
    if not supplier_id:
        await callback.message.answer("Ошибка: не найден ID поставщика для повторной отправки")
        await state.set_state(MySupplierStates.viewing_suppliers)
        return
    
    # Отправляем поставщика на повторную проверку
    reapplied = await DBService.reapply_supplier_static(supplier_id)
    
    if reapplied:
        # Получаем обновленный список поставщиков
        suppliers = await DBService.get_user_suppliers_static(callback.from_user.id)
        
        # Находим индекс текущего поставщика в обновленном списке
        current_index = 0
        for i, supplier in enumerate(suppliers):
            if supplier["id"] == supplier_id:
                current_index = i
                break
        
        # Получаем данные о поставщике для отправки в чат администраторов
        supplier_data = await DBService.get_supplier_by_id_static(supplier_id)
        
        # Отправляем уведомление в чат администраторов
        try:
            from app.services import admin_chat_service
            
            # Подготавливаем данные поставщика для админского уведомления
            admin_supplier_data = {
                "company_name": supplier_data.get("company_name", ""),
                "product_name": supplier_data.get("product_name", ""),
                "category_name": supplier_data.get("main_category_name", ""),
                "subcategory_name": supplier_data.get("category_name", ""),
                "description": supplier_data.get("description", "Не указано"),
                "photos": supplier_data.get("photos", [])
            }
            
            # Отправляем карточку поставщика с кнопкой "Забрать себе"
            result = await admin_chat_service.send_supplier_to_admin_chat(
                bot=bot,
                supplier_id=supplier_id,
                supplier_data=admin_supplier_data
            )
            
            if result:
                app_logger.info(f"Уведомление о повторной отправке поставщика ID:{supplier_id} отправлено в чат администраторов")
            else:
                app_logger.warning(f"Не удалось отправить уведомление в чат администраторов о поставщике ID:{supplier_id}")
                
        except Exception as e:
            app_logger.error(f"Ошибка при отправке уведомления в чат администраторов: {str(e)}")
        
        # Обновляем данные в состоянии
        await state.update_data(
            user_suppliers=suppliers,
            current_index=current_index
        )
        
        # Уведомляем об успешной отправке
        await callback.message.answer("Поставщик успешно отправлен на повторную проверку!")
        
        # Отображаем обновленную карточку
        supplier = suppliers[current_index]
        keyboard = create_supplier_navigation_keyboard(supplier, current_index, len(suppliers))
        
        # Устанавливаем состояние просмотра поставщиков
        await state.set_state(MySupplierStates.viewing_suppliers)
        
        # Отправляем новую карточку
        result = await send_supplier_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            supplier=supplier,
            keyboard=keyboard,
            show_status=True
        )
        
        # Обновляем ID сообщений в состоянии
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
    else:
        await callback.message.answer(
            "Произошла ошибка при отправке поставщика на повторную проверку. Пожалуйста, попробуйте позже."
        )
        await state.set_state(MySupplierStates.viewing_suppliers)

@router.callback_query(MySupplierStates.confirm_reapply, F.data == "cancel_reapply")
async def cancel_reapply(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для отмены повторной отправки поставщика на проверку.
    """
    await callback.answer()
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Возвращаемся к состоянию просмотра
    await state.set_state(MySupplierStates.viewing_suppliers)
    
    await callback.message.answer("Повторная отправка отменена.")

# Обработчик для кнопки редактирования (заглушка, будет реализована позже)
@router.callback_query(MySupplierStates.viewing_suppliers, F.data.startswith("edit_supplier:"))
async def edit_supplier(callback: CallbackQuery):
    """
    Обработчик для редактирования поставщика (заглушка).
    """
    await callback.answer()
    
    # Здесь будет реализован функционал редактирования поставщика
    await callback.message.answer(
        "Функционал редактирования поставщика будет реализован в следующем обновлении. "
        "Пока вы можете удалить поставщика и создать нового."
    )

# Обработчик для кнопки с текущим индексом поставщика
@router.callback_query(MySupplierStates.viewing_suppliers, F.data == "current_my_supplier")
async def handle_current_my_supplier(callback: CallbackQuery):
    """
    Обработчик для кнопки с текущим индексом поставщика.
    Просто отвечает на колбэк без действий, чтобы кнопка не мерцала.
    """
    await callback.answer()

# Функция регистрации обработчиков в основном диспетчере
def register_handlers(dp):
    """Register all handlers from this module"""
    dp.include_router(router) 