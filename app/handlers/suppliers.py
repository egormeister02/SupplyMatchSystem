"""
Обработчики для создания и управления поставщиками
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
import tempfile
import os
import time

from app.services import get_db_session, DBService, admin_chat_service
from app.states.states import SupplierCreationStates
from app.states.state_config import get_state_config
from app.utils.message_utils import (
    remove_keyboard_from_context,
    edit_message_text_and_keyboard,
)
from app.services.local_storage import local_storage_service
from app.config.logging import app_logger

# Initialize router
router = Router()

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
        bot: Объект бота для вызова show_supplier_confirmation
        
    Returns:
        bool: True если мы в режиме редактирования и нужно вернуться к подтверждению
    """
    state_data = await state.get_data()
    if state_data.get("editing_attribute") == attribute_name:
        # Сообщаем об обновлении и возвращаемся к подтверждению
        await message.answer(f"{attribute_name.replace('_', ' ').capitalize()} обновлен(а).")
        
        # Удаляем флаг редактирования, чтобы избежать зацикливания
        await state.update_data(editing_attribute=None)
        
        await show_supplier_confirmation(message, state, bot)
        return True
    return False

# Обработчики для ввода данных о поставщике
@router.message(SupplierCreationStates.waiting_company_name)
async def process_company_name(message: Message, state: FSMContext, bot: Bot):

    company_name = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(company_name) < 2:
        await message.answer("Название компании должно содержать не менее 2 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    await state.update_data(company_name=company_name)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "company_name", bot):
        return
    
    main_category_config = get_state_config(SupplierCreationStates.waiting_main_category)
    
    categories_text = await main_category_config["text_func"](state)
    
    await message.answer(
        categories_text,
        reply_markup=main_category_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_main_category)

@router.message(SupplierCreationStates.waiting_main_category)
async def process_main_category(message: Message, state: FSMContext, bot: Bot):

    try:
        category_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        state_data = await state.get_data()
        main_categories = state_data.get("main_categories", [])
        
        if not main_categories or category_number < 1 or category_number > len(main_categories):

            main_category_config = get_state_config(SupplierCreationStates.waiting_main_category)
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
        
        subcategory_config = get_state_config(SupplierCreationStates.waiting_subcategory)
        
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
        
        await state.set_state(SupplierCreationStates.waiting_subcategory)
        
    except ValueError:

        main_category_config = get_state_config(SupplierCreationStates.waiting_main_category)
        categories_text = await main_category_config["text_func"](state)
        
        await message.answer(
            f"{main_category_config['error_text']}\n\n{categories_text}",
            reply_markup=main_category_config.get("markup")
        )

@router.message(SupplierCreationStates.waiting_subcategory)
async def process_subcategory(message: Message, state: FSMContext, bot: Bot):
    """Обработка выбора подкатегории"""
    try:
        subcategory_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        state_data = await state.get_data()
        subcategories = state_data.get("subcategories", [])
        selected_category = state_data.get("main_category", "")
        
        if not subcategories or subcategory_number < 1 or subcategory_number > len(subcategories):

            subcategory_config = get_state_config(SupplierCreationStates.waiting_subcategory)
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
        
        product_name_config = get_state_config(SupplierCreationStates.waiting_product_name)
        
        await message.answer(
            product_name_config["text"],
            reply_markup=product_name_config.get("markup")
        )
        await state.set_state(SupplierCreationStates.waiting_product_name)
        
    except ValueError:

        subcategory_config = get_state_config(SupplierCreationStates.waiting_subcategory)
        state_data = await state.get_data()
        selected_category = state_data.get("main_category", "")
        subcategories_text, _ = await subcategory_config["text_func"](selected_category, state)
        
        await message.answer(
            f"{subcategory_config['error_text']}\n\n{subcategories_text}",
            reply_markup=subcategory_config.get("markup")
        )

@router.message(SupplierCreationStates.waiting_product_name)
async def process_product_name(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода названия продукта"""
    product_name = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(product_name) < 2:
        await message.answer("Название продукта должно содержать не менее 2 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    await state.update_data(product_name=product_name)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "product_name", bot):
        return
    
    description_config = get_state_config(SupplierCreationStates.waiting_description)
    
    await message.answer(
        description_config["text"],
        reply_markup=description_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_description)

@router.message(SupplierCreationStates.waiting_description)
async def process_description(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода описания продукта"""
    description = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(description) < 10:
        await message.answer("Описание должно содержать не менее 10 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    await state.update_data(description=description)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "description", bot):
        return
    
    # Переходим к вводу страны вместо местоположения
    country_config = get_state_config(SupplierCreationStates.waiting_country)
    
    await message.answer(
        country_config["text"],
        reply_markup=country_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_country)

@router.message(SupplierCreationStates.waiting_country)
async def process_country(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода страны"""
    country = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(country) < 2:
        await message.answer("Название страны должно содержать не менее 2 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    await state.update_data(country=country)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "country", bot):
        return
    
    # Переходим к вводу региона
    region_config = get_state_config(SupplierCreationStates.waiting_region)
    
    await message.answer(
        region_config["text"],
        reply_markup=region_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_region)

@router.message(SupplierCreationStates.waiting_region)
async def process_region(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода региона"""
    region = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    await state.update_data(region=region)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "region", bot):
        return
    
    # Переходим к вводу города
    city_config = get_state_config(SupplierCreationStates.waiting_city)
    
    await state.set_state(SupplierCreationStates.waiting_city)


@router.message(SupplierCreationStates.waiting_city)
async def process_city(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода города"""
    city = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    await state.update_data(city=city)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "city", bot):
        return
    
    # Переходим к вводу адреса
    address_config = get_state_config(SupplierCreationStates.waiting_address)
    
    await message.answer(
        address_config["text"],
        reply_markup=address_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_address)


@router.message(SupplierCreationStates.waiting_address)
async def process_address(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода адреса"""
    address = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    await state.update_data(address=address)
    
    # Проверяем, находимся ли мы в режиме редактирования
    if await check_if_editing(message, state, "address", bot):
        return
    
    # Переходим к загрузке фотографий
    photos_config = get_state_config(SupplierCreationStates.waiting_additional_photos)
    
    await message.answer(
        "Загрузите фотографии товара/услуги (до 8 штук).\nВы можете отправить несколько фото одним сообщением или пропустить этот шаг.",
        reply_markup=photos_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_additional_photos)
    
    await state.update_data(photos=[])


@router.message(SupplierCreationStates.waiting_additional_photos, F.photo)
async def process_photos(message: Message, state: FSMContext, bot: Bot):
    """Обработка загрузки фотографий"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        photos = state_data.get("photos", [])
        
        # Наилучшее качество фото из Telegram - это последнее в массиве photo
        best_photo = message.photo[-1]  # Самое высокое разрешение
        
        # Логируем информацию о фото для отладки
        app_logger.info(f"Получено фото: file_id={best_photo.file_id}, размер={best_photo.width}x{best_photo.height}")
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
                original_name=f"photo_{len(photos) + 1}.jpg"
            )
            
            # Добавляем информацию о фото в список
            photos.append({
                "file_id": best_photo.file_id,
                "storage_path": storage_path
            })
            
            # Обновляем список фото в состоянии
            await state.update_data(photos=photos)
            app_logger.info(f"Фото сохранено, всего фото: {len(photos)}")
            
            # Получаем конфигурацию для состояния
            photos_config = get_state_config(SupplierCreationStates.waiting_additional_photos)
            
            # Текст сообщения с информацией о загруженных фото
            photo_text = f"Загружено {len(photos)}/8 фото. Вы можете загрузить еще или перейти к следующему шагу."
            
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
        app_logger.error(f"Error saving photo: {e}")
        app_logger.error(f"File ID: {best_photo.file_id}")
        await message.answer("Произошла ошибка при сохранении фото. Пожалуйста, попробуйте еще раз или перейдите к следующему шагу.")


@router.message(SupplierCreationStates.waiting_video, F.video)
async def process_video(message: Message, state: FSMContext, bot: Bot):
    """Обработка загрузки видео"""
    try:
        # Получаем видео из сообщения
        video = message.video
        
        # Получаем файл от Telegram
        file = await bot.get_file(video.file_id)
        file_path = await bot.download_file(file.file_path)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            # Записываем содержимое в временный файл
            temp_file.write(file_path.read())
            temp_path = temp_file.name
        
        try:
            # Сохраняем файл в локальное хранилище
            storage_path = await local_storage_service.save_file(
                temp_path,
                original_name=f"video_{video.file_id}.mp4"
            )
            
            # Сохраняем информацию о видео в состояние
            await state.update_data(video={
                "file_id": video.file_id,
                "storage_path": storage_path
            })
            
            # Переходим к вводу контактных данных
            await proceed_to_username(message, state, bot)
            
        finally:
            # Удаляем временный файл
            os.unlink(temp_path)
            
    except Exception as e:
        app_logger.error(f"Error saving video: {e}")
        await message.answer("Произошла ошибка при сохранении видео. Пожалуйста, попробуйте еще раз.")
        # Устанавливаем видео как None при ошибке
        await state.update_data(video=None)
        # Продолжаем к следующему шагу
        await proceed_to_username(message, state, bot)

@router.callback_query(SupplierCreationStates.waiting_video, F.data == "skip_video")
async def skip_video(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка пропуска загрузки видео"""
    await callback.answer()
    
    # Устанавливаем None для видео
    await state.update_data(video=None)
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Переходим к вводу контактных данных
    await proceed_to_username(callback.message, state, bot)

async def proceed_to_username(message: Message, state: FSMContext, bot: Bot):
    """Переход к вводу Telegram username"""
    # Получаем конфигурацию для ввода username
    username_config = get_state_config(SupplierCreationStates.waiting_tg_username)
    
    # Устанавливаем состояние ввода username
    await state.set_state(SupplierCreationStates.waiting_tg_username)
    
    # Отправляем сообщение с запросом username
    await message.answer(
        username_config["text"],
        reply_markup=username_config.get("markup")
    )

@router.message(SupplierCreationStates.waiting_tg_username)
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

@router.callback_query(SupplierCreationStates.waiting_tg_username, F.data == "use_my_username")
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
    phone_config = get_state_config(SupplierCreationStates.waiting_phone)
    
    # Устанавливаем состояние ввода телефона
    await state.set_state(SupplierCreationStates.waiting_phone)
    
    # Проверяем, есть ли телефон в данных пользователя
    state_data = await state.get_data()
    has_profile_phone = state_data.get("phone") is not None

    # Отправляем сообщение с запросом телефона
    await message.answer(
        phone_config["text"],
        reply_markup=phone_config.get("markup")
    )

@router.message(SupplierCreationStates.waiting_phone, F.contact)
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

@router.message(SupplierCreationStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода телефона вручную или команды"""
    text = message.text.strip()
    
    if text.lower() == "отмена":
        # Возвращаемся к вводу телефона с обычной клавиатурой, убираем сначала текущую клавиатуру
        await message.answer("Отмена выбора контакта.", reply_markup=ReplyKeyboardRemove())
        
        phone_config = get_state_config(SupplierCreationStates.waiting_phone)
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

@router.callback_query(SupplierCreationStates.waiting_phone, F.data == "share_contact")
async def request_contact(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Запрос на отправку контакта"""
    await callback.answer()
    
    # Получаем конфигурацию для ввода телефона
    phone_config = get_state_config(SupplierCreationStates.waiting_phone)
    
    # Удаляем клавиатуру у текущего сообщения
    await remove_keyboard_from_context(bot, callback)
    
    # Отправляем сообщение с клавиатурой для отправки контакта
    await callback.message.answer(
        text="Отправьте ваш контактный номер, нажав на кнопку или введите вручную:",
        reply_markup=phone_config.get("share_contact_markup")
    )

@router.callback_query(SupplierCreationStates.waiting_phone, F.data == "use_profile_phone")
async def use_profile_phone(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Использование телефона из профиля пользователя"""
    await callback.answer()
    
    # Получаем данные пользователя
    state_data = await state.get_data()
    phone = state_data.get("phone")
    
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

# Модифицируем функцию перехода к email, чтобы она очищала клавиатуру
async def proceed_to_email(message: Message, state: FSMContext, bot: Bot):
    """Переход к вводу email"""
    # Очищаем клавиатуру перед сменой состояния
    await clear_reply_keyboard(message.chat.id, bot)
    
    # Получаем конфигурацию для ввода email
    email_config = get_state_config(SupplierCreationStates.waiting_email)
    
    # Устанавливаем состояние ввода email
    await state.set_state(SupplierCreationStates.waiting_email)
    
    # Отправляем сообщение с запросом email
    await message.answer(
        email_config["text"],
        reply_markup=email_config.get("markup")
    )

@router.message(SupplierCreationStates.waiting_email)
async def process_email(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода email"""
    email = message.text.strip()
    
    # Проверяем формат email
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        # Сохраняем email в состояние
        await state.update_data(contact_email=email)
        
        # Проверяем, находимся ли мы в режиме редактирования
        if await check_if_editing(message, state, "contact_email", bot):
            return
        
        # Сообщаем о получении email
        await message.answer(f"Получен email: {email}")
        
        # Переходим к подтверждению создания поставщика
        await show_supplier_confirmation(message, state, bot, is_edit=False)
    else:
        # Неверный формат email
        await message.answer(
            "Пожалуйста, введите email в корректном формате (например, example@domain.com) или используйте кнопки для других вариантов."
        )

@router.callback_query(SupplierCreationStates.waiting_email, F.data == "use_profile_email")
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
        
        # Переходим к подтверждению создания поставщика
        await show_supplier_confirmation(callback.message, state, bot, is_edit=False)
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
    # Переходим к подтверждению создания поставщика
    await show_supplier_confirmation(callback.message, state, bot, is_edit=True)

# Обновляем функцию подтверждения
async def show_supplier_confirmation(message: Message, state: FSMContext, bot: Bot, is_edit: bool = False):
    """Показывает информацию для подтверждения создания поставщика"""
    # Получаем данные из состояния
    state_data = await state.get_data()
    
    # Создаем текст подтверждения
    confirmation_text = "Пожалуйста, проверьте введенные данные о поставщике:\n\n"
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
    
    # Получаем конфигурацию для состояния подтверждения
    confirm_config = get_state_config(SupplierCreationStates.confirm_supplier_creation)
    
    # Устанавливаем состояние подтверждения
    await state.set_state(SupplierCreationStates.confirm_supplier_creation)
    
    # Отправляем сообщение с подтверждением
    if is_edit:
        await message.edit_text(
            confirmation_text,
            reply_markup=confirm_config.get("markup")
        )
    else:
        await message.answer(
            confirmation_text,
            reply_markup=confirm_config.get("markup")
        )

@router.callback_query(SupplierCreationStates.confirm_supplier_creation, F.data == "edit_attributes")
async def edit_supplier_attributes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик кнопки редактирования атрибутов поставщика"""
    await callback.answer()
    await remove_keyboard_from_context(bot, callback)
    # Получаем конфигурацию для выбора атрибута
    edit_config = get_state_config(SupplierCreationStates.select_attribute_to_edit)
    attributes = edit_config.get("attributes", [])
    
    # Формируем нумерованный список атрибутов
    attributes_text = edit_config.get("text", "Выберите, что вы хотите отредактировать (введите номер):") + "\n\n"
    for idx, attr in enumerate(attributes, 1):
        attributes_text += f"{idx}. {attr['display']}\n"
    
    # Устанавливаем состояние выбора атрибута
    await state.set_state(SupplierCreationStates.select_attribute_to_edit)
    
    # Сохраняем список атрибутов в состоянии
    await state.update_data(edit_attributes=attributes)
    
    # Отправляем сообщение с выбором атрибутов
    await callback.message.answer(
        attributes_text,
        reply_markup=edit_config.get("markup")
    )

@router.message(SupplierCreationStates.select_attribute_to_edit)
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
        if edit_state == SupplierCreationStates.waiting_main_category:
            # Для выбора категории нужно использовать специальную функцию
            text = await state_config["text_func"](state)
        elif edit_state == SupplierCreationStates.waiting_subcategory:
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
    await state.set_state(SupplierCreationStates.select_attribute_to_edit)
    
    # Получаем конфигурацию для выбора атрибута
    edit_config = get_state_config(SupplierCreationStates.select_attribute_to_edit)
    
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

# Обновляем функцию сохранения поставщика
@router.callback_query(SupplierCreationStates.confirm_supplier_creation, F.data == "confirm")
async def confirm_supplier_creation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение создания поставщика"""
    await callback.answer()
    
    # Получаем все данные из состояния
    state_data = await state.get_data()
    app_logger.info("=== Подтверждение создания поставщика ===")
    app_logger.info(f"ID пользователя: {callback.from_user.id}")
    
    try:
        # Сохраняем поставщика в базу данных
        app_logger.info("Начинаю процесс сохранения поставщика в БД")
        
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
            
            supplier_id = await db_service.save_supplier(
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
                created_by_id=state_data.get("user_id"),
                photos=state_data.get("photos", []),
                video=state_data.get("video")
            )
            
            app_logger.info(f"Поставщик успешно создан с ID: {supplier_id}")
            
            if not supplier_id:
                app_logger.error("Не удалось получить ID поставщика после создания")
                raise Exception("Ошибка при сохранении поставщика")
            
            # Создаем набор данных для отправки в чат администраторов
            supplier_data = {
                "company_name": state_data.get("company_name", ""),
                "product_name": state_data.get("product_name", ""),
                "category_name": state_data.get("main_category", ""),
                "subcategory_name": state_data.get("subcategory_name", ""),
                "description": state_data.get("description", "Не указано"),
                "photos": state_data.get("photos", [])
            }
            
            # Отправляем уведомление в чат администраторов
            try:
                # Отправляем карточку поставщика с кнопкой "Забрать себе"
                result = await admin_chat_service.send_supplier_to_admin_chat(
                    bot=bot,
                    supplier_id=supplier_id,
                    supplier_data=supplier_data
                )
                
                if result:
                    app_logger.info(f"Уведомление о новом поставщике отправлено в чат администраторов")
                else:
                    app_logger.warning("Не удалось отправить уведомление в чат администраторов")
                
            except Exception as e:
                app_logger.error(f"Ошибка при отправке уведомления в чат администраторов: {str(e)}")
            
            # Удаляем клавиатуру у текущего сообщения
            await remove_keyboard_from_context(bot, callback)
            
            # Формируем сообщение об успешном создании
            success_message = f"Поставщик успешно создан! Данные будут проверены администратором.\n"
            await callback.message.answer(success_message)
            
            # Возвращаемся в меню поставщиков
            from app.config.action_config import get_action_config
            action_config = get_action_config("suppliers")
            
            await callback.message.answer(
                action_config.get("text", "Меню поставщиков:"),
                reply_markup=action_config.get("markup")
            )
            
            # Очищаем состояние
            await state.clear()
            app_logger.info("=== Создание поставщика успешно завершено ===")
            
    except Exception as e:
        # Логируем ошибку
        app_logger.error(f"=== ОШИБКА при создании поставщика: {str(e)} ===")
        app_logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        app_logger.error(f"Стек вызовов: {traceback.format_exc()}")
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем пользователю об ошибке
        await callback.message.answer(
            "К сожалению, произошла ошибка при создании поставщика. Пожалуйста, попробуйте позже."
    )

def register_handlers(dp):
    dp.include_router(router) 