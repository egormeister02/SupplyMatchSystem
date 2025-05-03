"""
Обработчики для действий без состояний.
Используется для сценариев с простой навигацией по меню.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from app.utils.message_utils import remove_keyboard_from_context, edit_message_text_and_keyboard
from app.config.action_config import get_action_config
from app.states.states import SupplierCreationStates, RequestCreationStates
from app.states.state_config import get_state_config
from app.handlers.my_requests import show_user_requests

# Инициализируем роутер
router = Router()

@router.callback_query(F.data.in_(["suppliers", "requests_list", "favorites_list", "help_action",
                               "my_suppliers"]))
async def handle_menu_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для пунктов меню без состояний.
    Получает текст и клавиатуру из конфигурации действий.
    """
    await callback.answer()
    
    # Получаем действие из callback_data
    action = callback.data
    logging.info(f"Обрабатываю действие меню: {action}")
    
    # Получаем конфигурацию для действия
    action_config = get_action_config(action)
    
    if not action_config:
        await callback.message.answer("Неизвестное действие")
        return
    
    try:
        # Получаем информацию о сообщении
        message_id = callback.message.message_id
        chat_id = callback.message.chat.id
        has_text = bool(callback.message.text)
        has_caption = bool(callback.message.caption)
        has_photo = bool(callback.message.photo)
        has_media = bool(callback.message.photo or callback.message.video or callback.message.audio or callback.message.document)
        
        # Логируем информацию о сообщении
        logging.info(f"Сообщение {message_id} в чате {chat_id}:")
        logging.info(f"- Имеет текст: {has_text}")
        logging.info(f"- Имеет подпись: {has_caption}")
        logging.info(f"- Имеет фото: {has_photo}")
        logging.info(f"- Имеет медиа: {has_media}")
        
        # Кнопка "Назад" всегда должна создавать новое сообщение для сообщений с медиа
        # Просто отправляем новое сообщение и удаляем старое
        logging.info("Создаю новое сообщение и удаляю старое")
        
        # 1. Отправляем новое сообщение
        new_message = await callback.message.answer(
            action_config.get("text", "Выполняется действие..."),
            reply_markup=action_config.get("markup")
        )
        logging.info(f"Новое сообщение создано с ID: {new_message.message_id}")
        
        # 2. Пытаемся удалить старое сообщение
        try:
            await callback.message.delete()
            logging.info(f"Старое сообщение {message_id} удалено")
        except Exception as e:
            logging.warning(f"Не удалось удалить старое сообщение: {str(e)}")
            
    except Exception as e:
        logging.error(f"Ошибка при обработке действия меню: {str(e)}")
        await callback.message.answer(
            "Произошла ошибка при выполнении действия. Пожалуйста, попробуйте позже."
        )

@router.callback_query(F.data == "my_requests")
async def handle_my_requests(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки "Мои заявки".
    Показывает список заявок пользователя.
    """
    await callback.answer()
    
    # Удаляем сообщение меню
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение меню: {e}")
        
    # Показываем список заявок пользователя
    await show_user_requests(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        state=state,
        bot=bot
    )

@router.callback_query(F.data == "create_supplier")
async def handle_create_supplier(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для начала процесса создания поставщика.
    Переводит пользователя в состояние ввода названия компании.
    """
    await callback.answer()
    
    # Получаем информацию о пользователе из БД
    from app.services import get_db_session, DBService
    
    async with get_db_session() as session:
        db_service = DBService(session)
        user_data = await db_service.get_user_by_id(callback.from_user.id)
        
    if not user_data:
        await callback.message.answer(
            "Невозможно создать поставщика. Пожалуйста, сначала пройдите регистрацию через команду /start."
        )
        return
    
    # Сохраняем информацию о пользователе в состояние
    await state.update_data(
        user_id=user_data["tg_id"],
        username=user_data["username"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        email=user_data["email"],
        phone=user_data["phone"]
    )
    
    # Получаем конфигурацию для первого состояния создания поставщика
    company_name_config = get_state_config(SupplierCreationStates.waiting_company_name)
    
    # Устанавливаем состояние ввода названия компании
    await state.set_state(SupplierCreationStates.waiting_company_name)
    
    # Редактируем текущее сообщение
    result = await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=company_name_config["text"],
        reply_markup=company_name_config.get("markup")
    )
    
    # Если редактирование не удалось, отправляем новое сообщение
    if not result:
        await callback.message.answer(
            company_name_config["text"],
            reply_markup=company_name_config.get("markup")
        )

@router.callback_query(F.data == "create_request")
async def handle_create_request(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для начала процесса создания заявки.
    Переводит пользователя в состояние выбора категории.
    """
    await callback.answer()
    
    # Логируем начало создания заявки
    logging.info(f"Начало создания заявки пользователем: {callback.from_user.id}")
    
    # Получаем информацию о пользователе из БД
    from app.services import get_db_session, DBService
    
    async with get_db_session() as session:
        db_service = DBService(session)
        user_data = await db_service.get_user_by_id(callback.from_user.id)
        
    if not user_data:
        await callback.message.answer(
            "Невозможно создать заявку. Пожалуйста, сначала пройдите регистрацию через команду /start."
        )
        return
    
    # Получаем конфигурацию для первого состояния создания заявки
    main_category_config = get_state_config(RequestCreationStates.waiting_main_category)
    
    # Явно очищаем предыдущее состояние перед установкой нового
    await state.clear()
    
    # Сохраняем информацию о пользователе в состояние ПОСЛЕ очистки
    await state.update_data(
        user_id=user_data["tg_id"],
        username=user_data["username"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        email=user_data["email"],
        phone=user_data["phone"]
    )
    
    logging.info(f"Сохранена информация о пользователе в состояние: {user_data}")
    
    # Получаем текст с категориями
    categories_text = await main_category_config["text_func"](state)
    
    # Устанавливаем состояние выбора категории
    await state.set_state(RequestCreationStates.waiting_main_category)
    logging.info(f"Установлено состояние выбора категории для пользователя {callback.from_user.id}")
    
    # Редактируем текущее сообщение
    result = await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=categories_text,
        reply_markup=main_category_config.get("markup")
    )
    
    # Если редактирование не удалось, отправляем новое сообщение
    if not result:
        await callback.message.answer(
            categories_text,
            reply_markup=main_category_config.get("markup")
        )

@router.callback_query(F.data.startswith("back_to_action:"))
async def handle_back_to_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки возврата к действию.
    Формат callback_data: back_to_action:{action_name}
    Например: back_to_action:main_menu
    """
    await callback.answer()
    
    # Получаем имя действия из callback_data
    target_action = callback.data.replace("back_to_action:", "")
    logging.info(f"Обрабатываю возврат к действию: {target_action}")
    
    # Получаем конфигурацию для целевого действия
    action_config = get_action_config(target_action)
    
    if not action_config:
        await callback.message.answer("Конфигурация для указанного действия не найдена")
        return
    
    try:
        # Получаем информацию о сообщении
        message_id = callback.message.message_id
        chat_id = callback.message.chat.id
        
        logging.info(f"Создаю новое сообщение и удаляю старое для действия back_to_action:{target_action}")
        
        # 1. Отправляем новое сообщение
        new_message = await callback.message.answer(
            action_config.get("text", "Возврат к предыдущему меню"),
            reply_markup=action_config.get("markup")
        )
        logging.info(f"Новое сообщение создано с ID: {new_message.message_id}")
        
        # 2. Пытаемся удалить старое сообщение
        try:
            await callback.message.delete()
            logging.info(f"Старое сообщение {message_id} удалено")
        except Exception as e:
            logging.warning(f"Не удалось удалить старое сообщение: {str(e)}")
            
    except Exception as e:
        logging.error(f"Ошибка при обработке возврата к действию: {str(e)}")
        await callback.message.answer(
            "Произошла ошибка при выполнении действия. Пожалуйста, попробуйте позже."
        )

# Добавление роутера в основной диспетчер
def register_handlers(dp):
    """Register action handlers"""
    dp.include_router(router) 