"""
Обработчики для создания и управления заявками
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
import tempfile
import os
import time
import re
from pathlib import Path

from app.services import get_db_session, DBService
from app.states.states import RequestCreationStates
from app.states.state_config import get_state_config
from app.utils.message_utils import (
    remove_keyboard_from_context,
    edit_message_text_and_keyboard,
)
from app.services.local_storage import local_storage_service
from app.config.logging import app_logger
from app.keyboards.inline import get_back_button, get_back_keyboard

# Initialize router with specific name for debugging
router = Router(name="requests_handlers")

# Глобальный словарь для хранения времени последнего фото в группе
last_photo_times = {}

# Глобальный словарь для отслеживания обработанных групп медиа
processed_media_groups = {}

# Словарь для отслеживания сообщений для медиа групп
media_group_messages = {}

# Вспомогательная функция для проверки режима редактирования
async def check_if_editing(message: Message, state: FSMContext, attribute_name: str, bot: Bot = None):
    """
    Проверяет, находимся ли мы в режиме редактирования атрибута
    
    Args:
        message: Объект сообщения
        state: Контекст состояния
        attribute_name: Имя редактируемого атрибута
        bot: Объект бота для вызова show_request_confirmation
        
    Returns:
        bool: True если мы в режиме редактирования и нужно вернуться к подтверждению
    """
    state_data = await state.get_data()
    if state_data.get("editing_attribute") == attribute_name:
        # Сообщаем об обновлении и возвращаемся к подтверждению
        await message.answer(f"{attribute_name.replace('_', ' ').capitalize()} обновлен(о).")
        
        # Удаляем флаг редактирования, чтобы избежать зацикливания
        await state.update_data(editing_attribute=None)
        
        # Возвращаемся к подтверждению
        await show_request_confirmation(message, state, bot)
        return True
    return False

# Обновленный обработчик для выбора категории, чтобы лучше отлавливать сообщения с числами
@router.message(RequestCreationStates.waiting_main_category)
async def process_main_category(message: Message, state: FSMContext, bot: Bot):
    """Обработка выбора основной категории для заявки"""
    app_logger.info(f"Получено сообщение для выбора категории: {message.text}")
    
    # Получаем конфигурацию и состояние до проверки ввода
    main_category_config = get_state_config(RequestCreationStates.waiting_main_category)
    state_data = await state.get_data()
    main_categories = state_data.get("main_categories", [])
    
    # Если категории не были загружены, загружаем их сейчас
    if not main_categories:
        categories_text = await main_category_config["text_func"](state)
        state_data = await state.get_data()  # Обновляем данные после вызова функции
        main_categories = state_data.get("main_categories", [])
        
        # Если категории все еще не загружены, выводим сообщение об ошибке
        if not main_categories:
            await message.answer(
                "Не удалось загрузить категории. Пожалуйста, попробуйте еще раз.",
                reply_markup=main_category_config.get("markup")
            )
            return
    
    try:
        category_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        if category_number < 1 or category_number > len(main_categories):
            categories_text = await main_category_config["text_func"](state)
            
            await message.answer(
                f"{main_category_config['error_text']}\n\n{categories_text}",
                reply_markup=main_category_config.get("markup")
            )
            return
        
        selected_category = main_categories[category_number - 1]["name"]
        
        await state.update_data(main_category=selected_category)
        
        # Проверяем, находимся ли мы в режиме редактирования
        if await check_if_editing(message, state, "main_category", bot):
            return
        
        subcategory_config = get_state_config(RequestCreationStates.waiting_subcategory)
        
        subcategories_text, success = await subcategory_config["text_func"](selected_category, state)
        
        if not success:
            await message.answer(
                subcategories_text,
                reply_markup=main_category_config.get("markup")
            )
            return
        
        await message.answer(
            subcategories_text,
            reply_markup=subcategory_config.get("markup")
        )
        
        await state.set_state(RequestCreationStates.waiting_subcategory)
        
    except ValueError:
        app_logger.error(f"Ошибка преобразования текста '{message.text}' в число")
        categories_text = await main_category_config["text_func"](state)
        
        await message.answer(
            f"{main_category_config['error_text']}\n\n{categories_text}",
            reply_markup=main_category_config.get("markup")
        )

@router.message(RequestCreationStates.waiting_subcategory)
async def process_subcategory(message: Message, state: FSMContext, bot: Bot):
    """Обработка выбора подкатегории для заявки"""
    # Получаем конфигурацию и данные до проверки ввода
    subcategory_config = get_state_config(RequestCreationStates.waiting_subcategory)
    state_data = await state.get_data()
    subcategories = state_data.get("subcategories", [])
    selected_category = state_data.get("main_category", "")
    
    # Если подкатегории не были загружены, загружаем их сейчас
    if not subcategories and selected_category:
        subcategories_text, success = await subcategory_config["text_func"](selected_category, state)
        if not success:
            await message.answer(
                subcategories_text,
                reply_markup=subcategory_config.get("markup")
            )
            return
            
        state_data = await state.get_data()  # Обновляем данные после вызова функции
        subcategories = state_data.get("subcategories", [])
    
    try:
        subcategory_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        if not subcategories or subcategory_number < 1 or subcategory_number > len(subcategories):
            subcategories_text, _ = await subcategory_config["text_func"](selected_category, state)
            
            await message.answer(
                f"{subcategory_config['error_text']}\n\n{subcategories_text}",
                reply_markup=subcategory_config.get("markup")
            )
            return
        
        selected_subcategory = subcategories[subcategory_number - 1]
        
        await state.update_data(
            category_id=selected_subcategory["id"],
            subcategory_name=selected_subcategory["name"]
        )
        
        # Проверяем, находимся ли мы в режиме редактирования
        if await check_if_editing(message, state, "subcategory_name", bot):
            return
        
        description_config = get_state_config(RequestCreationStates.waiting_description)
        
        await message.answer(
            description_config["text"],
            reply_markup=description_config.get("markup")
        )
        await state.set_state(RequestCreationStates.waiting_description)
        
    except ValueError:
        subcategories_text, _ = await subcategory_config["text_func"](selected_category, state)
        
        await message.answer(
            f"{subcategory_config['error_text']}\n\n{subcategories_text}",
            reply_markup=subcategory_config.get("markup")
        )

@router.message(RequestCreationStates.waiting_description)
async def process_description(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода описания заявки"""
    description = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(description) < 10:
        await message.answer("Описание должно содержать не менее 10 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    await state.update_data(description=description)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "description", bot):
        return
    
    # Переходим к загрузке фотографий
    photos_config = get_state_config(RequestCreationStates.waiting_photos)
    
    await message.answer(
        photos_config["text"],
        reply_markup=photos_config.get("markup")
    )
    
    await state.set_state(RequestCreationStates.waiting_photos)
    
    # Инициализируем список фотографий
    await state.update_data(photos=[])

@router.message(RequestCreationStates.waiting_photos, F.photo)
async def process_photos(message: Message, state: FSMContext, bot: Bot):
    """Обработка загрузки фотографий к заявке"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        photos = state_data.get("photos", [])
        
        # Проверяем лимит фотографий
        if len(photos) >= 3:
            await message.answer("Вы уже загрузили максимальное количество фотографий (3). Перейдите к следующему шагу.")
            return
        
        # Наилучшее качество фото из Telegram - это последнее в массиве photo
        best_photo = message.photo[-1]  # Самое высокое разрешение
        
        # Логируем информацию о фото для отладки
        app_logger.info(f"Получено фото для заявки: file_id={best_photo.file_id}, размер={best_photo.width}x{best_photo.height}")
        app_logger.info(f"Является частью группы: {message.media_group_id is not None}")
        
        is_new_photo = True  # Флаг для отслеживания, новое ли это фото
        
        # Проверяем, является ли это часть группы и обрабатывали ли мы уже эту фотографию
        if message.media_group_id:
            # Если группа уже обрабатывалась, проверяем не обрабатывали ли мы это фото
            group_data = processed_media_groups.get(message.media_group_id, {"photos": []})
            if best_photo.file_id in group_data["photos"]:
                app_logger.info(f"Фото {best_photo.file_id} из группы {message.media_group_id} уже обработано")
                return
            
            # Добавляем file_id в список обработанных для этой группы
            group_data["photos"].append(best_photo.file_id)
            group_data["last_time"] = time.time()
            processed_media_groups[message.media_group_id] = group_data
            app_logger.info(f"Добавлено фото в группу {message.media_group_id}, всего фото в группе: {len(group_data['photos'])}")
        
        # Сохраняем фото в локальное хранилище
        file = await bot.get_file(best_photo.file_id)
        file_path = await bot.download_file(file.file_path)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(file_path.read())
            temp_path = temp_file.name
        
        try:
            # Сохраняем файл в локальное хранилище
            storage_path = await local_storage_service.save_file(
                temp_path,
                original_name=f"request_photo_{len(photos) + 1}.jpg"
            )
            
            # Добавляем информацию о фото в список
            photos.append({
                "file_id": best_photo.file_id,
                "storage_path": storage_path
            })
            
            # Обновляем список фото в состоянии
            await state.update_data(photos=photos)
            app_logger.info(f"Фото для заявки сохранено, всего фото: {len(photos)}")
            
            # Получаем конфигурацию для состояния
            photos_config = get_state_config(RequestCreationStates.waiting_photos)
            
            # Текст сообщения с информацией о загруженных фото
            photo_text = f"Загружено {len(photos)}/3 фото. Вы можете загрузить еще или перейти к следующему шагу."
            
            # Если это часть группы медиа
            if message.media_group_id:
                # Проверяем, есть ли уже сообщение для этой группы
                if message.media_group_id in media_group_messages:
                    # Если есть, редактируем его
                    try:
                        msg_data = media_group_messages[message.media_group_id]
                        await bot.edit_message_text(
                            photo_text,
                            chat_id=message.chat.id,
                            message_id=msg_data["message_id"],
                            reply_markup=photos_config.get("markup")
                        )
                        app_logger.info(f"Сообщение для группы {message.media_group_id} обновлено")
                    except Exception as e:
                        app_logger.error(f"Ошибка при обновлении сообщения: {e}")
                else:
                    # Если нет, отправляем новое
                    new_message = await message.answer(
                        photo_text,
                        reply_markup=photos_config.get("markup")
                    )
                    # Сохраняем информацию о сообщении
                    media_group_messages[message.media_group_id] = {
                        "message_id": new_message.message_id,
                        "chat_id": message.chat.id
                    }
                    app_logger.info(f"Создано новое сообщение для группы {message.media_group_id}")
            else:
                # Если это одиночное фото, просто отправляем сообщение
                await message.answer(
                    photo_text,
                    reply_markup=photos_config.get("markup")
                )
                app_logger.info("Отправлено сообщение для одиночного фото")
            
        finally:
            # Удаляем временный файл
            os.unlink(temp_path)
            
    except Exception as e:
        app_logger.error(f"Error saving photo for request: {e}")
        await message.answer("Произошла ошибка при сохранении фото. Пожалуйста, попробуйте еще раз или перейдите к следующему шагу.")

@router.callback_query(RequestCreationStates.waiting_photos, F.data == "confirm_request_creation")
async def proceed_to_confirmation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к подтверждению создания заявки"""
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Переходим к подтверждению создания заявки
    await show_request_confirmation(callback.message, state, bot)

@router.callback_query(RequestCreationStates.waiting_photos, F.data == "waiting_tg_username")
async def proceed_to_username(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход к вводу Telegram username"""
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Получаем конфигурацию для ввода username
    username_config = get_state_config(RequestCreationStates.waiting_tg_username)
    
    # Устанавливаем состояние ввода username
    await state.set_state(RequestCreationStates.waiting_tg_username)
    
    # Отправляем сообщение с запросом username
    await callback.message.answer(
        username_config["text"],
        reply_markup=username_config.get("markup")
    )

@router.message(RequestCreationStates.waiting_tg_username)
async def process_tg_username(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода Telegram username"""
    username = message.text.strip()
    
    # Проверяем корректность username
    if not username.startswith('@'):
        username = '@' + username
    
    # Сохраняем username в состояние
    await state.update_data(contact_username=username)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "contact_username", bot):
        return
    
    # Сообщаем о получении username
    await message.answer(f"Получен контактный username: {username}")
    
    # Переходим к вводу телефона
    await proceed_to_phone(message, state, bot)

@router.callback_query(RequestCreationStates.waiting_tg_username, F.data == "use_my_username")
async def use_my_username(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Использование собственного username пользователя"""
    await callback.answer()
    
    # Получаем username пользователя
    username = callback.from_user.username
    
    if username:
        # Добавляем @ к username, если его нет
        if not username.startswith('@'):
            username = '@' + username
            
        # Сохраняем username в состояние
        await state.update_data(contact_username=username)
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем о выборе
        await callback.message.edit_text(f"Установлен контактный username: {username}")
        
        # Переходим к вводу телефона
        await proceed_to_phone(callback.message, state, bot)
    else:
        # Если у пользователя нет username
        await callback.message.answer(
            "У вас не установлен username в Telegram. Пожалуйста, введите другой контактный username или установите свой в настройках Telegram."
        )

async def proceed_to_phone(message: Message, state: FSMContext, bot: Bot):
    """Переход к вводу телефона"""
    # Получаем конфигурацию для ввода телефона
    phone_config = get_state_config(RequestCreationStates.waiting_phone)
    
    # Устанавливаем состояние ввода телефона
    await state.set_state(RequestCreationStates.waiting_phone)
    
    # Проверяем, есть ли телефон в данных пользователя
    state_data = await state.get_data()
    has_profile_phone = state_data.get("phone") is not None

    # Отправляем сообщение с запросом телефона
    await message.answer(
        phone_config["text"],
        reply_markup=phone_config.get("markup")
    )

@router.message(RequestCreationStates.waiting_phone, F.contact)
async def process_contact(message: Message, state: FSMContext, bot: Bot):
    """Обработка полученного контакта"""
    # Получаем объект контакта
    contact = message.contact
    
    # Сохраняем телефон в состояние
    await state.update_data(contact_phone=contact.phone_number)
    
    # Сообщаем о получении телефона и удаляем клавиатуру
    await message.answer(
        f"Получен номер телефона: {contact.phone_number}", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Переходим к вводу email
    await proceed_to_email(message, state, bot)

@router.message(RequestCreationStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода телефона вручную или команды"""
    text = message.text.strip()
    
    if text.lower() == "отмена":
        # Возвращаемся к вводу телефона с обычной клавиатурой, убираем сначала текущую клавиатуру
        await message.answer("Отмена выбора контакта.", reply_markup=ReplyKeyboardRemove())
        
        phone_config = get_state_config(RequestCreationStates.waiting_phone)
        await message.answer(
            phone_config["text"],
            reply_markup=phone_config.get("markup")
        )
        return
    
    # Проверяем формат телефона
    if text.startswith('+') and len(text) > 10:
        # Сохраняем телефон в состояние
        await state.update_data(contact_phone=text)
        
        # Проверяем, находимся ли мы в режиме редактирования
        if await check_if_editing(message, state, "contact_phone", bot):
            return
        
        # Удаляем клавиатуру и сообщаем о получении телефона
        await message.answer(
            f"Получен номер телефона: {text}", 
            reply_markup=ReplyKeyboardRemove()
        )
        
        await proceed_to_email(message, state, bot)
    else:
        await message.answer(
            "Пожалуйста, введите номер телефона в международном формате (например, +79001234567) или нажмите кнопку 'Отмена'."
        )

@router.callback_query(RequestCreationStates.waiting_phone, F.data == "share_contact")
async def request_contact(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос на отправку контакта"""
    await callback.answer()
    
    # Получаем конфигурацию для ввода телефона
    phone_config = get_state_config(RequestCreationStates.waiting_phone)
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Отправляем сообщение с клавиатурой для отправки контакта
    await callback.message.answer(
        text="Отправьте ваш контактный номер, нажав на кнопку или введите вручную:",
        reply_markup=phone_config.get("share_contact_markup")
    )

@router.callback_query(RequestCreationStates.waiting_phone, F.data == "use_profile_phone")
async def use_profile_phone(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Использование телефона из профиля пользователя"""
    await callback.answer()
    
    # Получаем данные пользователя
    state_data = await state.get_data()
    phone = state_data.get("phone")
    
    # Логируем данные для отладки
    app_logger.info(f"Используется телефон из профиля. Текущие данные в state: {state_data}")
    
    # Проверка напрямую из базы данных на случай, если в state не сохранилось
    if not phone:
        app_logger.info(f"Телефон не найден в state, запрашиваем из базы данных")
        async with get_db_session() as session:
            db_service = DBService(session)
            user_data = await db_service.get_user_by_id(callback.from_user.id)
            if user_data and user_data.get("phone"):
                phone = user_data.get("phone")
                # Обновляем данные в состоянии
                await state.update_data(phone=phone)
                app_logger.info(f"Получен телефон из базы данных: {phone}")
    
    if phone:
        # Сохраняем телефон в состояние
        await state.update_data(contact_phone=phone)
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем о выборе
        await callback.message.answer(f"Установлен телефон: {phone}")
        
        # Переходим к вводу email
        await proceed_to_email(callback.message, state, bot)
    else:
        # Если в профиле нет телефона
        await callback.message.answer(
            "В вашем профиле не найден телефон. Пожалуйста, введите телефон вручную или поделитесь контактом."
        )

@router.callback_query(RequestCreationStates.waiting_phone, F.data == "waiting_email")
async def skip_phone(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Пропуск ввода телефона"""
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Переходим к вводу email
    await proceed_to_email(callback.message, state, bot)

# Добавляем функцию для очистки клавиатуры при смене состояния
async def clear_reply_keyboard(chat_id: int, bot: Bot):
    """Отправляет пустое сообщение с ReplyKeyboardRemove для очистки клавиатуры"""
    try:
        message = await bot.send_message(
            chat_id=chat_id, 
            text="\u200B",  # Zero-width space
            reply_markup=ReplyKeyboardRemove()
        )
        # Удаляем сообщение сразу после отправки
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception as e:
        app_logger.error(f"Ошибка при очистке клавиатуры: {e}")

async def proceed_to_email(message: Message, state: FSMContext, bot: Bot):
    """Переход к вводу email"""
    # Очищаем клавиатуру перед сменой состояния
    await clear_reply_keyboard(message.chat.id, bot)
    
    # Получаем конфигурацию для ввода email
    email_config = get_state_config(RequestCreationStates.waiting_email)
    
    # Устанавливаем состояние ввода email
    await state.set_state(RequestCreationStates.waiting_email)
    
    # Отправляем сообщение с запросом email
    await message.answer(
        email_config["text"],
        reply_markup=email_config.get("markup")
    )

@router.message(RequestCreationStates.waiting_email)
async def process_email(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода email"""
    email = message.text.strip()
    
    # Проверяем формат email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        # Сохраняем email в состояние
        await state.update_data(contact_email=email)
        
        # Проверяем, находимся ли мы в режиме редактирования
        if await check_if_editing(message, state, "contact_email", bot):
            return
        
        # Сообщаем о получении email
        await message.answer(f"Получен email: {email}")
        
        # Переходим к подтверждению создания заявки
        await show_request_confirmation(message, state, bot)
    else:
        # Неверный формат email
        await message.answer(
            "Пожалуйста, введите email в корректном формате (например, example@domain.com) или используйте кнопки для других вариантов."
        )

@router.callback_query(RequestCreationStates.waiting_email, F.data == "use_profile_email")
async def use_profile_email(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Использование email из профиля пользователя"""
    await callback.answer()
    
    # Получаем данные пользователя
    state_data = await state.get_data()
    email = state_data.get("email")
    
    if email:
        # Сохраняем email в состояние
        await state.update_data(contact_email=email)
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем о выборе
        await callback.message.answer(f"Установлен email: {email}")
        
        # Переходим к подтверждению создания заявки
        await show_request_confirmation(callback.message, state, bot)
    else:
        # Если в профиле нет email
        await callback.message.answer(
            "В вашем профиле не найден email. Пожалуйста, введите email вручную или пропустите этот шаг."
        )

@router.callback_query(F.data == "skip_email")
async def skip_email(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Пропуск ввода email"""
    await callback.answer()
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    # Переходим к подтверждению создания заявки
    await show_request_confirmation(callback.message, state, bot)

async def show_request_confirmation(message: Message, state: FSMContext, bot: Bot):
    """Показывает информацию для подтверждения создания заявки"""
    # Получаем данные из состояния
    state_data = await state.get_data()
    
    # Создаем текст подтверждения
    confirmation_text = "Пожалуйста, проверьте введенные данные заявки:\n\n"
    confirmation_text += f"Категория: {state_data.get('main_category', '')}\n"
    confirmation_text += f"Подкатегория: {state_data.get('subcategory_name', '')}\n"
    confirmation_text += f"Описание: {state_data.get('description', '')}\n"
    
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
    
    # Получаем конфигурацию для состояния подтверждения
    confirm_config = get_state_config(RequestCreationStates.confirm_request_creation)
    
    # Устанавливаем состояние подтверждения
    await state.set_state(RequestCreationStates.confirm_request_creation)
    
    # Отправляем сообщение с подтверждением
    await message.answer(
        confirmation_text,
        reply_markup=confirm_config.get("markup")
    )

@router.callback_query(RequestCreationStates.confirm_request_creation, F.data == "edit_attributes")
async def edit_request_attributes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки редактирования атрибутов заявки"""
    await callback.answer()
    await remove_keyboard_from_context(bot, callback)
    
    # Получаем конфигурацию для выбора атрибута
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

@router.message(RequestCreationStates.select_attribute_to_edit)
async def process_attribute_selection(message: Message, state: FSMContext, bot: Bot):
    """Обработка выбора атрибута для редактирования"""
    try:
        # Пытаемся получить номер атрибута
        attr_number = int(message.text.strip())
        await remove_keyboard_from_context(bot, message)
        
        # Получаем данные состояния
        state_data = await state.get_data()
        attributes = state_data.get("edit_attributes", [])
        
        # Проверяем корректность номера
        if attr_number < 1 or attr_number > len(attributes):
            await message.answer("Пожалуйста, выберите корректный номер атрибута из списка.")
            return
        
        # Получаем выбранный атрибут
        selected_attr = attributes[attr_number - 1]
        
        # Сохраняем выбранный атрибут для возврата после редактирования
        await state.update_data(editing_attribute=selected_attr["name"])
        
        # Получаем состояние для редактирования атрибута
        edit_state = selected_attr["state"]
        
        # Получаем конфигурацию для этого состояния
        state_config = get_state_config(edit_state)
        
        # Подготавливаем текст и клавиатуру для редактирования выбранного атрибута
        if edit_state == RequestCreationStates.waiting_main_category:
            # Для выбора категории нужно использовать специальную функцию
            text = await state_config["text_func"](state)
        elif edit_state == RequestCreationStates.waiting_subcategory:
            # Для выбора подкатегории также нужна специальная функция
            main_category = state_data.get("main_category", "")
            text, _ = await state_config["text_func"](main_category, state)
        else:
            # Для остальных атрибутов используем стандартный текст
            text = f"Редактирование: {selected_attr['display']}\n\n" + state_config.get("text", "Введите новое значение:")
        
        # Задаем состояние редактирования
        await state.set_state(edit_state)
        
        # Отправляем сообщение для редактирования
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Вернуться к списку атрибутов", callback_data="back_to_attributes")]
                ]
            )
        )
        
    except ValueError:
        await message.answer("Пожалуйста, введите номер атрибута из списка.")

@router.callback_query(F.data == "back_to_attributes")
async def back_to_attribute_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки возврата к списку атрибутов"""
    await callback.answer()
    
    # Устанавливаем состояние выбора атрибута
    await state.set_state(RequestCreationStates.select_attribute_to_edit)
    
    # Получаем конфигурацию для выбора атрибута
    edit_config = get_state_config(RequestCreationStates.select_attribute_to_edit)
    
    # Получаем данные состояния
    state_data = await state.get_data()
    attributes = state_data.get("edit_attributes", [])
    
    # Формируем нумерованный список атрибутов
    attributes_text = edit_config.get("text", "Выберите, что вы хотите отредактировать (введите номер):") + "\n\n"
    for idx, attr in enumerate(attributes, 1):
        attributes_text += f"{idx}. {attr['display']}\n"
    
    # Отправляем сообщение с выбором атрибутов
    await edit_message_text_and_keyboard(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=attributes_text,
        reply_markup=edit_config.get("markup")
    )

@router.callback_query(F.data == "back_to_confirm")
async def back_to_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки возврата к подтверждению заявки"""
    await callback.answer()
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Переходим к подтверждению создания заявки
    await show_request_confirmation(callback.message, state, bot)

@router.callback_query(RequestCreationStates.confirm_request_creation, F.data == "confirm_request")
async def confirm_request_creation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение создания заявки"""
    await callback.answer()
    
    # Получаем все данные из состояния
    state_data = await state.get_data()
    app_logger.info("=== Подтверждение создания заявки ===")
    app_logger.info(f"ID пользователя: {callback.from_user.id}")
    
    try:
        # Сохраняем заявку в базу данных
        app_logger.info("Начинаю процесс сохранения заявки в БД")
        
        async with get_db_session() as session:
            db_service = DBService(session)
            
            # Проверяем правильность структуры фотографий
            photos = state_data.get("photos", [])
            if photos:
                for i, photo in enumerate(photos):
                    if not isinstance(photo, dict):
                        app_logger.error(f"Неверный формат фото {i}: {photo}")
                        photos[i] = None
                    elif 'storage_path' not in photo:
                        app_logger.error(f"У фото {i} отсутствует storage_path: {photo}")
                        photos[i] = None
                
                # Фильтруем некорректные фотографии
                photos = [p for p in photos if p is not None]
                app_logger.info(f"После проверки осталось {len(photos)} корректных фотографий")
                # Обновляем список фотографий
                await state.update_data(photos=photos)
                state_data = await state.get_data()
            
            # Создаем запрос SQL для вставки заявки с контактными данными
            query = """
            INSERT INTO requests (
                category_id, 
                description, 
                created_by_id, 
                contact_username, 
                contact_phone, 
                contact_email,
                created_at, 
                status
            )
            VALUES (
                :category_id, 
                :description, 
                :created_by_id, 
                :contact_username, 
                :contact_phone, 
                :contact_email,
                NOW(), 
                'pending'
            )
            RETURNING id;
            """
            
            # Параметры для запроса
            params = {
                "category_id": state_data.get("category_id"),
                "description": state_data.get("description"),
                "created_by_id": callback.from_user.id,
                "contact_username": state_data.get("contact_username"),
                "contact_phone": state_data.get("contact_phone"),
                "contact_email": state_data.get("contact_email")
            }
            
            # Выполняем запрос и получаем ID новой заявки
            result = await db_service.execute_query(query, params)
            row = result.fetchone()
            request_id = row[0] if row else None
            
            # Сохраняем фотографии в базу данных
            if request_id and photos:
                for photo in photos:
                    await db_service.save_file(
                        file_path=photo["storage_path"],
                        file_type="image",
                        name=None,
                        request_id=request_id
                    )
            
            # Фиксируем транзакцию
            await db_service.commit()
            
            app_logger.info(f"Заявка успешно создана с ID: {request_id}")
            
            # Отправляем уведомление в чат администраторов
            try:
                from app.services import admin_chat_service
                
                # Используем данные из state вместо запроса к БД
                main_category_name = state_data.get("main_category", "")
                category_name = state_data.get("subcategory_name", "")
                
                # Подготавливаем данные заявки для админского уведомления
                admin_request_data = {
                    "id": request_id,
                    "description": state_data.get("description", ""),
                    "main_category_name": main_category_name,
                    "category_name": category_name,
                    "contact_username": state_data.get("contact_username", ""),
                    "contact_phone": state_data.get("contact_phone", ""),
                    "contact_email": state_data.get("contact_email", ""),
                    "photos": photos
                }
                
                # Отправляем заявку в чат администраторов с помощью нового метода
                result = await admin_chat_service.send_request_to_admin_chat(
                    bot=bot,
                    request_id=request_id,
                    request_data=admin_request_data
                )
                
                if result:
                    app_logger.info(f"Заявка {request_id} успешно отправлена в чат администраторов")
                else:
                    app_logger.warning(f"Не удалось отправить заявку {request_id} в чат администраторов")
                
            except Exception as e:
                app_logger.error(f"Ошибка при отправке уведомления в чат администраторов: {str(e)}")
                import traceback
                app_logger.error(f"Трассировка: {traceback.format_exc()}")
            
            # Удаляем клавиатуру у текущего сообщения
            await remove_keyboard_from_context(bot, callback)
            
            # Формируем сообщение об успешном создании
            success_message = f"Заявка успешно создана, и отправлена на проверку администратору.\n"
            await callback.message.answer(success_message)
            
            # Возвращаемся в меню заявок
            from app.config.action_config import get_action_config
            action_config = get_action_config("requests_list")
            
            await callback.message.answer(
                action_config.get("text", "Меню заявок:"),
                reply_markup=action_config.get("markup")
            )
            
            # Очищаем состояние
            await state.clear()
            app_logger.info("=== Создание заявки успешно завершено ===")
            
    except Exception as e:
        # Логируем ошибку
        app_logger.error(f"=== ОШИБКА при создании заявки: {str(e)} ===")
        app_logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        app_logger.error(f"Стек вызовов: {traceback.format_exc()}")
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем пользователю об ошибке
        await callback.message.answer(
            "К сожалению, произошла ошибка при создании заявки. Пожалуйста, попробуйте позже."
        )

def register_handlers(dp):
    dp.include_router(router) 