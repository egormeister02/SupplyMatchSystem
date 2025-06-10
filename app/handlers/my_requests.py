"""
Обработчики для управления заявками пользователя (раздел "Мои заявки").
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from app.states.states import MyRequestStates, RequestCreationStates
from app.services import get_db_session, DBService
from app.utils.message_utils import send_request_card
from app.config.action_config import get_action_config
from app.config.logging import app_logger
from app.keyboards.inline import get_back_button, get_main_user_menu_keyboard
from app.states.state_config import get_state_config

# Инициализируем роутер
router = Router()

# Функция-хелпер для показа списка заявок пользователя без использования callback
async def show_user_requests(user_id: int, chat_id: int, state: FSMContext, bot: Bot):
    """
    Вспомогательная функция для отображения списка заявок пользователя.
    Может быть вызвана напрямую из других обработчиков.
    
    Args:
        user_id (int): ID пользователя
        chat_id (int): ID чата для отправки сообщений
        state (FSMContext): Контекст состояния
        bot (Bot): Экземпляр бота
    """
    try:
        # Получаем список заявок пользователя
        requests = await DBService.get_user_requests_static(user_id)
        
        # Если заявок нет
        if not requests:
            await bot.send_message(
                chat_id=chat_id,
                text="У вас пока нет созданных заявок. Вы можете создать новую заявку через меню заявок."
            )
            return
            
        # Сохраняем список заявок в состояние
        await state.update_data(
            user_requests=requests,
            current_index=0
        )
        
        # Устанавливаем состояние просмотра
        await state.set_state(MyRequestStates.viewing_requests)
        
        # Получаем текущий индекс и заявку
        current_index = 0
        request = requests[current_index]
        
        # Создаем клавиатуру для навигации и управления
        keyboard = create_request_navigation_keyboard(request, current_index, len(requests))
        
        # Получаем количество откликов на заявку, если она одобрена
        matches_count = None
        if request.get("status") == "approved":
            matches_count = await DBService.get_matches_count_for_request(request.get("id"))
        
        # Отправляем карточку заявки
        result = await send_request_card(
            bot=bot,
            chat_id=chat_id,
            request=request,
            keyboard=keyboard,
            show_status=True,  # Показываем статус заявки
            matches_count=matches_count  # Передаем количество откликов
        )
        
        # Сохраняем message_id для дальнейшего использования
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
        
    except Exception as e:
        app_logger.error(f"Ошибка при получении заявок пользователя: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при загрузке ваших заявок. Пожалуйста, попробуйте позже."
        )

# Обработчик для кнопки "Показать мои заявки"
@router.callback_query(F.data == "view_my_requests")
async def handle_view_my_requests(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для кнопки просмотра своих заявок.
    Показывает список заявок пользователя.
    """
    await callback.answer()
    
    # Проверяем, нужно ли удалять предыдущее сообщение
    try:
        # Пытаемся удалить сообщение с кнопкой
        if callback.data == "view_my_requests":
            await callback.message.delete()
    except Exception as e:
        app_logger.warning(f"Не удалось удалить предыдущее сообщение: {e}")
    
    # Вызываем общую функцию для показа заявок
    await show_user_requests(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        state=state,
        bot=bot
    )

# Функция для создания клавиатуры навигации по заявкам
def create_request_navigation_keyboard(request, current_index, total_count):
    """
    Создает клавиатуру для навигации и управления заявкой.
    
    Args:
        request (dict): Данные заявки
        current_index (int): Текущий индекс в списке
        total_count (int): Общее количество заявок
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для управления заявкой
    """
    # Основные кнопки навигации
    navigation_row = [
        InlineKeyboardButton(text="◀️", callback_data="prev_my_request"),
        InlineKeyboardButton(text=f"{current_index + 1}/{total_count}", callback_data="current_my_request"),
        InlineKeyboardButton(text="▶️", callback_data="next_my_request")
    ]
    
    # Определяем дополнительные кнопки в зависимости от статуса
    status = request.get("status", "pending")
    request_id = request.get("id")
    
    keyboard = []
    keyboard.append(navigation_row)
    
    # Если заявка одобрена, добавляем кнопку просмотра откликов
    if status == "approved":
        keyboard.append([
            InlineKeyboardButton(text="🔍 Посмотреть отклики", callback_data=f"view_request_suppliers:{request_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_request:{request_id}")
        ])
    elif status == "rejected":
        # Для отклоненных заявок - удаление, редактирование, повторная отправка
        keyboard.append([
            InlineKeyboardButton(text="🔄 Отправить на повторную проверку", callback_data=f"reapply_request:{request_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_request:{request_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_request:{request_id}")
        ])
    
    # Добавляем кнопку возврата к меню
    keyboard.append([
        get_back_button("requests_list", is_state=False, button_text="Назад")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчик для кнопки "Следующая заявка"
@router.callback_query(MyRequestStates.viewing_requests, F.data == "next_my_request")
async def next_my_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к следующей заявке в списке.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    requests = state_data.get("user_requests", [])
    current_index = state_data.get("current_index", 0)
    
    # Рассчитываем следующий индекс (с цикличностью)
    next_index = (current_index + 1) % len(requests)
    
    # Получаем следующую заявку
    request = requests[next_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=next_index)
    
    # Создаем клавиатуру
    keyboard = create_request_navigation_keyboard(request, next_index, len(requests))
    
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
    
    # Получаем количество откликов на заявку, если она одобрена
    matches_count = None
    if request.get("status") == "approved":
        matches_count = await DBService.get_matches_count_for_request(request.get("id"))
    
    # Отправляем новую карточку
    result = await send_request_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        request=request,
        keyboard=keyboard,
        show_status=True,
        matches_count=matches_count  # Передаем количество откликов
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для кнопки "Предыдущая заявка"
@router.callback_query(MyRequestStates.viewing_requests, F.data == "prev_my_request")
async def prev_my_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к предыдущей заявке в списке.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    requests = state_data.get("user_requests", [])
    current_index = state_data.get("current_index", 0)
    
    # Рассчитываем предыдущий индекс (с цикличностью)
    prev_index = (current_index - 1) % len(requests)
    
    # Получаем предыдущую заявку
    request = requests[prev_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_index=prev_index)
    
    # Создаем клавиатуру
    keyboard = create_request_navigation_keyboard(request, prev_index, len(requests))
    
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
    
    # Получаем количество откликов на заявку, если она одобрена
    matches_count = None
    if request.get("status") == "approved":
        matches_count = await DBService.get_matches_count_for_request(request.get("id"))
    
    # Отправляем новую карточку
    result = await send_request_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        request=request,
        keyboard=keyboard,
        show_status=True,
        matches_count=matches_count  # Передаем количество откликов
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для удаления заявки (подтверждение)
@router.callback_query(MyRequestStates.viewing_requests, F.data.startswith("delete_request:"))
async def confirm_delete_request(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для запроса подтверждения удаления заявки.
    """
    await callback.answer()
    
    # Получаем ID заявки из callback_data
    request_id = int(callback.data.split(":")[1])
    
    # Сохраняем ID заявки для удаления
    await state.update_data(request_to_delete=request_id)
    
    # Устанавливаем состояние подтверждения удаления
    await state.set_state(MyRequestStates.confirm_delete)
    
    # Получаем конфигурацию для состояния подтверждения удаления
    state_config = get_state_config(MyRequestStates.confirm_delete)
    
    # Отправляем запрос на подтверждение используя конфигурацию
    await callback.message.answer(
        state_config["text"],
        reply_markup=state_config["markup"]
    )

# Обработчик для подтверждения удаления
@router.callback_query(MyRequestStates.confirm_delete, F.data == "confirm_delete")
async def delete_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для подтверждения удаления заявки.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    request_id = state_data.get("request_to_delete")
    
    # Получаем ID сообщений текущей карточки для удаления
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    if not request_id:
        await callback.message.answer("Ошибка: не найден ID заявки для удаления")
        await state.set_state(MyRequestStates.viewing_requests)
        return
    
    # Удаляем сообщения текущей карточки заявки
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
        
    # Выполняем удаление заявки
    deleted = await DBService.delete_request_static(request_id)
    
    if deleted:
        # Получаем обновленный список заявок
        requests = await DBService.get_user_requests_static(callback.from_user.id)
        
        if not requests:
            # Если больше нет заявок, возвращаемся в меню
            await callback.message.answer(
                "Заявка успешно удалена. У вас больше нет созданных заявок."
            )
            await state.clear()
            
            # Показываем меню заявок
            action_config = get_action_config("my_requests")
            await callback.message.answer(
                action_config["text"],
                reply_markup=action_config["markup"]
            )
            return
            
        # Обновляем список заявок в состоянии
        current_index = 0
        await state.update_data(
            user_requests=requests,
            current_index=current_index
        )
        
        # Уведомляем об успешном удалении
        await callback.message.answer("Заявка успешно удалена!")
        
        # Отображаем следующую заявку
        request = requests[current_index]
        keyboard = create_request_navigation_keyboard(request, current_index, len(requests))
        
        # Возвращаемся к состоянию просмотра заявок
        await state.set_state(MyRequestStates.viewing_requests)
        
        # Получаем количество откликов на заявку, если она одобрена
        matches_count = None
        if request.get("status") == "approved":
            matches_count = await DBService.get_matches_count_for_request(request.get("id"))
        
        # Отправляем новую карточку
        result = await send_request_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            request=request,
            keyboard=keyboard,
            show_status=True,
            matches_count=matches_count  # Передаем количество откликов
        )
        
        # Обновляем ID сообщений в состоянии
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
    else:
        await callback.message.answer(
            "Произошла ошибка при удалении заявки. Пожалуйста, попробуйте позже."
        )
        # Возвращаемся к состоянию просмотра
        await state.set_state(MyRequestStates.viewing_requests)

# Обработчик для отмены удаления
@router.callback_query(MyRequestStates.confirm_delete, F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для отмены удаления заявки.
    """
    await callback.answer()
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Возвращаемся к состоянию просмотра
    await state.set_state(MyRequestStates.viewing_requests)
    
    await callback.message.answer("Удаление отменено.")

# Обработчик для повторной отправки заявки на проверку
@router.callback_query(MyRequestStates.viewing_requests, F.data.startswith("reapply_request:"))
async def reapply_request_click(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для нажатия на кнопку "Отправить на повторную проверку".
    Запрашивает подтверждение у пользователя.
    """
    await callback.answer()
    
    # Получаем ID заявки из callback_data
    request_id = int(callback.data.split(":")[1])
    
    # Сохраняем ID заявки для повторной отправки
    await state.update_data(request_to_reapply=request_id)
    
    # Получаем информацию о заявке, чтобы показать причину отклонения
    request_data = await DBService.get_request_by_id_static(request_id)
    if not request_data:
        await callback.message.answer("Ошибка: не удалось получить информацию о заявке")
        return
    
    # Формируем сообщение с причиной отклонения (если она есть)
    rejection_reason = request_data.get("rejection_reason", "Причина не указана")
    
    # Получаем конфигурацию для состояния подтверждения повторной отправки
    state_config = get_state_config(MyRequestStates.confirm_reapply)
    
    # Создаем сообщение для подтверждения, добавляя причину отклонения
    confirm_text = f"Вы собираетесь отправить заявку #{request_data.get('id')} на повторную проверку.\n\n"
    confirm_text += f"❗️ Причина предыдущего отклонения: {rejection_reason}\n\n"
    confirm_text += "Подтверждаете отправку?"
    
    # Устанавливаем состояние подтверждения повторной отправки
    await state.set_state(MyRequestStates.confirm_reapply)
    
    # Отправляем запрос на подтверждение с клавиатурой из конфигурации
    await callback.message.answer(
        confirm_text,
        reply_markup=state_config["markup"]
    )

@router.callback_query(MyRequestStates.confirm_reapply, F.data == "confirm_reapply")
async def confirm_reapply_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для подтверждения повторной отправки заявки на проверку.
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    request_id = state_data.get("request_to_reapply")
    
    # Получаем ID сообщений текущей карточки для удаления
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Удаляем сообщения карточки заявки, так как они устарели
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
    
    if not request_id:
        await callback.message.answer("Ошибка: не найден ID заявки для повторной отправки")
        await state.set_state(MyRequestStates.viewing_requests)
        return
    
    # Отправляем заявку на повторную проверку
    reapplied = await DBService.reapply_request_static(request_id)
    
    if reapplied:
        # Получаем обновленный список заявок
        requests = await DBService.get_user_requests_static(callback.from_user.id)
        
        # Находим индекс текущей заявки в обновленном списке
        current_index = 0
        for i, request in enumerate(requests):
            if request["id"] == request_id:
                current_index = i
                break
        
        # Получаем данные о заявке для отправки в чат администраторов
        request_data = await DBService.get_request_by_id_static(request_id)
        
        # Отправляем уведомление в чат администраторов
        try:
            from app.services import admin_chat_service
            
            # Подготавливаем данные заявки для админского уведомления
            admin_request_data = {
                "id": request_data.get("id", ""),
                "category_name": request_data.get("category_name", ""),
                "main_category_name": request_data.get("main_category_name", ""),
                "description": request_data.get("description", "Не указано"),
                "photos": request_data.get("photos", []),
                "contact_username": request_data.get("contact_username", ""),
                "contact_phone": request_data.get("contact_phone", ""),
                "contact_email": request_data.get("contact_email", "")
            }
            
            # Отправляем карточку заявки в админский чат
            result = await admin_chat_service.send_request_to_admin_chat(
                bot=bot,
                request_id=request_id,
                request_data=admin_request_data
            )
            
            if result:
                app_logger.info(f"Уведомление о повторной отправке заявки ID:{request_id} отправлено в чат администраторов")
            else:
                app_logger.warning(f"Не удалось отправить уведомление в чат администраторов о заявке ID:{request_id}")
                
        except Exception as e:
            app_logger.error(f"Ошибка при отправке уведомления в чат администраторов: {str(e)}")
        
        # Обновляем данные в состоянии
        await state.update_data(
            user_requests=requests,
            current_index=current_index
        )
        
        # Уведомляем об успешной отправке
        await callback.message.answer("Заявка успешно отправлена на повторную проверку!")
        
        # Отображаем обновленную карточку
        request = requests[current_index]
        keyboard = create_request_navigation_keyboard(request, current_index, len(requests))
        
        # Устанавливаем состояние просмотра заявок
        await state.set_state(MyRequestStates.viewing_requests)
        
        # Получаем количество откликов на заявку, если она одобрена
        matches_count = None
        if request.get("status") == "approved":
            matches_count = await DBService.get_matches_count_for_request(request.get("id"))
        
        # Отправляем новую карточку
        result = await send_request_card(
            bot=bot,
            chat_id=callback.message.chat.id,
            request=request,
            keyboard=keyboard,
            show_status=True,
            matches_count=matches_count  # Передаем количество откликов
        )
        
        # Обновляем ID сообщений в состоянии
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
    else:
        await callback.message.answer(
            "Произошла ошибка при отправке заявки на повторную проверку. Пожалуйста, попробуйте позже."
        )
        await state.set_state(MyRequestStates.viewing_requests)

@router.callback_query(MyRequestStates.confirm_reapply, F.data == "cancel_reapply")
async def cancel_reapply(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для отмены повторной отправки заявки на проверку.
    """
    await callback.answer()
    
    # Удаляем сообщение с подтверждением
    await callback.message.delete()
    
    # Возвращаемся к состоянию просмотра
    await state.set_state(MyRequestStates.viewing_requests)
    
    await callback.message.answer("Повторная отправка отменена.")

# Обработчик для кнопки редактирования заявки
@router.callback_query(MyRequestStates.viewing_requests, F.data.startswith("edit_request:"))
async def edit_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для редактирования заявки.
    Получает данные заявки из БД и переходит в режим редактирования.
    """
    await callback.answer()
    
    try:
        # Получаем ID заявки из callback_data
        request_id = int(callback.data.split(":")[1])
        
        # Получаем полную информацию о заявке из БД
        request_data = await DBService.get_request_by_id_static(request_id)
        
        if not request_data:
            await callback.message.answer("Ошибка: не удалось получить информацию о заявке")
            return
        
        # Получаем данные существующей карточки для последующего восстановления
        state_data = await state.get_data()
        keyboard_message_id = state_data.get("keyboard_message_id")
        media_message_ids = state_data.get("media_message_ids", [])
        user_requests = state_data.get("user_requests", [])
        current_index = state_data.get("current_index", 0)
        
        # Сохраняем данные карточки для восстановления после редактирования
        await state.update_data(
            # Сохраняем данные для восстановления карточки
            saved_keyboard_message_id=keyboard_message_id,
            saved_media_message_ids=media_message_ids,
            saved_user_requests=user_requests,
            saved_current_index=current_index,
            saved_request_id=request_id
        )
        
        # Удаляем клавиатуру у карточки заявки и у сообщения-носителя клавиатуры
        try:
            # Проверяем, есть ли отдельное сообщение с клавиатурой
            if keyboard_message_id and keyboard_message_id not in media_message_ids:
                # Удаляем клавиатуру у сообщения-носителя
                await bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id, 
                    message_id=keyboard_message_id,
                    reply_markup=None
                )
                app_logger.info(f"Удалена клавиатура у сообщения-носителя {keyboard_message_id}")
            
            # Если у медиа сообщений есть клавиатура (например, у одиночного фото)
            for msg_id in media_message_ids:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=callback.message.chat.id, 
                        message_id=msg_id,
                        reply_markup=None
                    )
                    app_logger.info(f"Удалена клавиатура у медиа сообщения {msg_id}")
                except Exception as e:
                    # Игнорируем ошибки, если клавиатуры нет
                    pass
        except Exception as e:
            app_logger.error(f"Ошибка при удалении клавиатуры: {e}")
        
        # Сохраняем данные заявки в состояние для редактирования
        await state.update_data(
            # Основные данные
            request_id=request_id,  # ID заявки для обновления
            description=request_data.get("description", ""),
            
            # Данные о категории
            main_category=request_data.get("main_category_name", ""),
            subcategory_name=request_data.get("category_name", ""),
            category_id=request_data.get("category_id"),
            
            # Контактные данные
            contact_username=request_data.get("contact_username", ""),
            contact_phone=request_data.get("contact_phone", ""),
            contact_email=request_data.get("contact_email", ""),
            
            # Медиафайлы
            photos=request_data.get("photos", []),
            video=request_data.get("video"),
            
            # Устанавливаем флаги режима редактирования
            is_edit_mode=True,  # Флаг режима редактирования
            from_my_requests=True,  # Флаг, что редактирование началось из "Мои заявки"
            
            # Сохраняем статус заявки для проверки необходимости повторной отправки
            status=request_data.get("status", ""),
            
            # Сохраняем ID пользователя
            user_id=callback.from_user.id
        )
        
        # Сразу переходим к выбору атрибута для редактирования, минуя шаг подтверждения
        # Получаем конфигурацию для выбора атрибута
        from app.states.state_config import get_state_config
        from app.states.states import RequestCreationStates
        
        edit_config = get_state_config(RequestCreationStates.select_attribute_to_edit)
        attributes = edit_config.get("attributes", [])
        
        # Формируем нумерованный список атрибутов
        attributes_text = edit_config.get("text", "Выберите, что вы хотите отредактировать (введите номер):") + "\n\n"
        for idx, attr in enumerate(attributes, 1):
            attributes_text += f"{idx}. {attr['display']}\n"
        
        # Устанавливаем состояние выбора атрибута
        await state.set_state(RequestCreationStates.select_attribute_to_edit)
        
        # Сохраняем список атрибутов в состоянии
        await state.update_data(edit_attributes=attributes)
        
        # Отправляем сообщение с выбором атрибутов
        await callback.message.answer(
            attributes_text,
            reply_markup=edit_config.get("markup")
        )
        
    except Exception as e:
        app_logger.error(f"Ошибка при подготовке к редактированию заявки: {e}")
        await callback.message.answer(
            "Произошла ошибка при подготовке к редактированию заявки. Пожалуйста, попробуйте позже."
        )

# Функция восстановления карточки заявки после редактирования
async def restore_request_card(message: Message, state: FSMContext, bot: Bot):
    """
    Восстанавливает карточку заявки после редактирования.
    Используется при возврате в раздел "Мои заявки".
    
    Args:
        message: Объект сообщения
        state: Контекст состояния
        bot: Объект бота
    """
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        
        # Получаем обновленные данные заявки из БД
        request_id = state_data.get("saved_request_id")
        if not request_id:
            app_logger.error("Не найден ID заявки для восстановления карточки")
            await message.answer("Произошла ошибка при возврате к просмотру заявки. Пожалуйста, вернитесь в раздел 'Мои заявки'.")
            return
            
        request_data = await DBService.get_request_by_id_static(request_id)
        if not request_data:
            app_logger.error(f"Не удалось получить данные заявки {request_id} для восстановления карточки")
            await message.answer("Произошла ошибка при возврате к просмотру заявки. Пожалуйста, вернитесь в раздел 'Мои заявки'.")
            return
        
        # Обновляем список заявок пользователя
        requests = await DBService.get_user_requests_static(state_data.get("user_id"))
        
        # Находим индекс текущей заявки в списке
        current_index = 0
        for i, req in enumerate(requests):
            if req["id"] == request_id:
                current_index = i
                break
        
        # Устанавливаем состояние просмотра заявок
        await state.set_state(MyRequestStates.viewing_requests)
        
        # Обновляем данные в состоянии
        await state.update_data(
            user_requests=requests,
            current_index=current_index
        )
        
        # Сообщаем об успешном обновлении
        await message.answer("Данные заявки успешно обновлены!")
        
        # Создаем клавиатуру
        keyboard = create_request_navigation_keyboard(request_data, current_index, len(requests))
        
        # Получаем количество откликов на заявку, если она одобрена
        matches_count = None
        if request_data.get("status") == "approved":
            matches_count = await DBService.get_matches_count_for_request(request_id)
        
        # Отправляем карточку заявки
        result = await send_request_card(
            bot=bot,
            chat_id=message.chat.id,
            request=request_data,
            keyboard=keyboard,
            show_status=True,
            matches_count=matches_count
        )
        
        # Обновляем ID сообщений в состоянии
        await state.update_data(
            keyboard_message_id=result.get("keyboard_message_id"),
            media_message_ids=result.get("media_message_ids", [])
        )
    
    except Exception as e:
        app_logger.error(f"Ошибка при восстановлении карточки заявки: {e}")
        await message.answer("Произошла ошибка при возврате к просмотру заявки. Пожалуйста, вернитесь в раздел 'Мои заявки'.")

# Обработчик для кнопки с текущим индексом заявки
@router.callback_query(MyRequestStates.viewing_requests, F.data == "current_my_request")
async def handle_current_my_request(callback: CallbackQuery):
    """
    Обработчик для кнопки с текущим индексом заявки.
    Просто отвечает на колбэк без действий, чтобы кнопка не мерцала.
    """
    await callback.answer()

# Обработчик для просмотра откликов на заявку
@router.callback_query(MyRequestStates.viewing_requests, F.data.startswith("view_request_suppliers:"))
async def view_request_suppliers(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для просмотра поставщиков, откликнувшихся на заявку
    """
    await callback.answer()
    
    # Получаем ID заявки из callback_data
    request_id = int(callback.data.split(":")[1])
    
    # Получаем поставщиков, которые откликнулись на заявку
    suppliers = await DBService.get_suppliers_for_request(request_id)
    
    if not suppliers:
        await callback.message.answer("На данную заявку пока нет откликов от поставщиков.")
        return
    
    # Сохраняем данные в состоянии
    await state.update_data(
        request_suppliers=suppliers,
        current_supplier_index=0,
        request_id=request_id
    )
    
    # Устанавливаем состояние просмотра откликов
    await state.set_state(MyRequestStates.viewing_request_suppliers)
    
    # Получаем текущий индекс и поставщика
    current_index = 0
    supplier = suppliers[current_index]
    
    # Получаем ID сообщений карточки заявки для удаления
    state_data = await state.get_data()
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщения карточки заявки
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
    
    # Создаем клавиатуру для навигации по откликам
    keyboard = create_supplier_response_keyboard(supplier, current_index, len(suppliers), request_id, can_write_review=True)
    
    # Отправляем карточку поставщика
    from app.utils.message_utils import send_supplier_card
    result = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=supplier,
        keyboard=keyboard
    )
    
    # Сохраняем message_id для дальнейшего использования
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Функция для создания клавиатуры навигации по откликам
def create_supplier_response_keyboard(supplier, current_index, total_count, request_id, can_write_review=False):
    """
    Создает клавиатуру для навигации по откликам
    Args:
        supplier (dict): Данные поставщика
        current_index (int): Текущий индекс в списке
        total_count (int): Общее количество поставщиков
        request_id (int): ID заявки
        can_write_review (bool): Можно ли писать отзыв
    Returns:
        InlineKeyboardMarkup: Клавиатура для навигации
    """
    # Основные кнопки навигации
    navigation_row = [
        InlineKeyboardButton(text="◀️", callback_data="prev_request_supplier"),
        InlineKeyboardButton(text=f"{current_index + 1}/{total_count}", callback_data="current_request_supplier"),
        InlineKeyboardButton(text="▶️", callback_data="next_request_supplier")
    ]
    keyboard = []
    keyboard.append(navigation_row)
    # Кнопка "Написать отзыв"
    if can_write_review:
        keyboard.append([
            InlineKeyboardButton(text="✍️ Написать отзыв", callback_data=f"write_review:{supplier['id']}")
        ])
    # Добавляем кнопку возврата к заявке
    keyboard.append([
        InlineKeyboardButton(text="↩️ Назад к заявке", callback_data=f"back_to_request:{request_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчик для кнопки "Следующий поставщик"
@router.callback_query(MyRequestStates.viewing_request_suppliers, F.data == "next_request_supplier")
async def next_request_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к следующему поставщику в списке откликов
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("request_suppliers", [])
    current_index = state_data.get("current_supplier_index", 0)
    request_id = state_data.get("request_id")
    
    # Рассчитываем следующий индекс (с цикличностью)
    next_index = (current_index + 1) % len(suppliers)
    
    # Получаем следующего поставщика
    supplier = suppliers[next_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_supplier_index=next_index)
    
    # Создаем клавиатуру
    keyboard = create_supplier_response_keyboard(supplier, next_index, len(suppliers), request_id)
    
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
    from app.utils.message_utils import send_supplier_card
    result = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=supplier,
        keyboard=keyboard
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для кнопки "Предыдущий поставщик"
@router.callback_query(MyRequestStates.viewing_request_suppliers, F.data == "prev_request_supplier")
async def prev_request_supplier(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для перехода к предыдущему поставщику в списке откликов
    """
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    suppliers = state_data.get("request_suppliers", [])
    current_index = state_data.get("current_supplier_index", 0)
    request_id = state_data.get("request_id")
    
    # Рассчитываем предыдущий индекс (с цикличностью)
    prev_index = (current_index - 1) % len(suppliers)
    
    # Получаем предыдущего поставщика
    supplier = suppliers[prev_index]
    
    # Обновляем индекс в состоянии
    await state.update_data(current_supplier_index=prev_index)
    
    # Создаем клавиатуру
    keyboard = create_supplier_response_keyboard(supplier, prev_index, len(suppliers), request_id)
    
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
    from app.utils.message_utils import send_supplier_card
    result = await send_supplier_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        supplier=supplier,
        keyboard=keyboard
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для кнопки "Назад к заявке"
@router.callback_query(MyRequestStates.viewing_request_suppliers, F.data.startswith("back_to_request:"))
async def back_to_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обработчик для возврата к просмотру заявки
    """
    await callback.answer()
    
    # Получаем ID заявки
    request_id = int(callback.data.split(":")[1])
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    keyboard_message_id = state_data.get("keyboard_message_id")
    media_message_ids = state_data.get("media_message_ids", [])
    
    # Удаляем сообщения с карточкой поставщика
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
    
    # Получаем информацию о заявке
    request_data = await DBService.get_request_by_id_static(request_id)
    if not request_data:
        await callback.message.answer("Ошибка: не удалось получить информацию о заявке")
        await state.set_state(MyRequestStates.viewing_requests)
        return
    
    # Получаем список всех заявок пользователя
    user_requests = await DBService.get_user_requests_static(callback.from_user.id)
    
    # Находим индекс текущей заявки в списке
    current_index = 0
    for i, req in enumerate(user_requests):
        if req["id"] == request_id:
            current_index = i
            break
    
    # Обновляем данные в состоянии
    await state.update_data(
        user_requests=user_requests,
        current_index=current_index
    )
    
    # Устанавливаем состояние просмотра заявок
    await state.set_state(MyRequestStates.viewing_requests)
    
    # Создаем клавиатуру навигации по заявкам
    keyboard = create_request_navigation_keyboard(request_data, current_index, len(user_requests))
    
    # Получаем количество откликов на заявку
    matches_count = None
    if request_data.get("status") == "approved":
        matches_count = await DBService.get_matches_count_for_request(request_id)
    
    # Отправляем карточку заявки
    result = await send_request_card(
        bot=bot,
        chat_id=callback.message.chat.id,
        request=request_data,
        keyboard=keyboard,
        show_status=True,
        matches_count=matches_count
    )
    
    # Обновляем ID сообщений в состоянии
    await state.update_data(
        keyboard_message_id=result.get("keyboard_message_id"),
        media_message_ids=result.get("media_message_ids", [])
    )

# Обработчик для кнопки с текущим индексом поставщика
@router.callback_query(MyRequestStates.viewing_request_suppliers, F.data == "current_request_supplier")
async def handle_current_request_supplier(callback: CallbackQuery):
    """
    Обработчик для кнопки с текущим индексом поставщика.
    Просто отвечает на колбэк без действий, чтобы кнопка не мерцала.
    """
    await callback.answer()

# Функция регистрации обработчиков в основном диспетчере
def register_handlers(dp):
    """Register all handlers from this module"""
    dp.include_router(router) 