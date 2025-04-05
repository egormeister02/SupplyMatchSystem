"""
Обработчики для создания и управления поставщиками
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.services import get_db_session, DBService
from app.states.states import SupplierCreationStates
from app.states.state_config import get_state_config
from app.utils.message_utils import (
    remove_keyboard_from_context,
    edit_message_text_and_keyboard
)

# Initialize router
router = Router()

# Обработчики для ввода данных о поставщике
@router.message(SupplierCreationStates.waiting_company_name)
async def process_company_name(message: Message, state: FSMContext, bot: Bot):
    """Обработка ввода названия компании"""
    company_name = message.text.strip()
    
    await remove_keyboard_from_context(bot, message)
    
    if len(company_name) < 2:
        await message.answer("Название компании должно содержать не менее 2 символов. Пожалуйста, попробуйте еще раз.")
        return
    
    # Сохраняем название компании в состояние
    await state.update_data(company_name=company_name)
    
    # Получаем конфигурацию для состояния выбора главной категории
    main_category_config = get_state_config(SupplierCreationStates.waiting_main_category)
    
    # Получаем текст категорий через функцию из конфигурации
    categories_text = await main_category_config["text_func"](state)
    
    # Отправляем сообщение со списком категорий
    await message.answer(
        categories_text,
        reply_markup=main_category_config.get("markup")
    )
    
    await state.set_state(SupplierCreationStates.waiting_main_category)

@router.message(SupplierCreationStates.waiting_main_category)
async def process_main_category(message: Message, state: FSMContext, bot: Bot):
    """Обработка выбора основной категории"""
    try:
        category_number = int(message.text.strip())
        
        await remove_keyboard_from_context(bot, message)
        
        # Получаем данные о категориях из состояния
        state_data = await state.get_data()
        main_categories = state_data.get("main_categories", [])
        
        if not main_categories or category_number < 1 or category_number > len(main_categories):
            # Отправляем сообщение об ошибке и список категорий снова
            main_category_config = get_state_config(SupplierCreationStates.waiting_main_category)
            categories_text = await main_category_config["text_func"](state)
            
            await message.answer(
                f"{main_category_config['error_text']}\n\n{categories_text}",
                reply_markup=main_category_config.get("markup")
            )
            return
        
        # Получаем выбранную категорию
        selected_category = main_categories[category_number - 1]["name"]
        
        # Сохраняем выбранную категорию в состояние
        await state.update_data(main_category=selected_category)
        
        # Получаем конфигурацию для состояния выбора подкатегории
        subcategory_config = get_state_config(SupplierCreationStates.waiting_subcategory)
        
        # Получаем текст подкатегорий через функцию из конфигурации
        subcategories_text, success = await subcategory_config["text_func"](selected_category, state)
        
        if not success:
            await message.answer(
                subcategories_text,
                reply_markup=main_category_config.get("markup")
            )
            return
        
        # Отправляем сообщение со списком подкатегорий
        await message.answer(
            subcategories_text,
            reply_markup=subcategory_config.get("markup")
        )
        
        await state.set_state(SupplierCreationStates.waiting_subcategory)
        
    except ValueError:
        # Если пользователь ввел не число
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
        
        # Получаем данные о подкатегориях из состояния
        state_data = await state.get_data()
        subcategories = state_data.get("subcategories", [])
        selected_category = state_data.get("main_category", "")
        
        if not subcategories or subcategory_number < 1 or subcategory_number > len(subcategories):
            # Отправляем сообщение об ошибке и список подкатегорий снова
            subcategory_config = get_state_config(SupplierCreationStates.waiting_subcategory)
            subcategories_text, _ = await subcategory_config["text_func"](selected_category, state)
            
            await message.answer(
                f"{subcategory_config['error_text']}\n\n{subcategories_text}",
                reply_markup=subcategory_config.get("markup")
            )
            return
        
        # Получаем выбранную подкатегорию
        selected_subcategory = subcategories[subcategory_number - 1]
        
        # Сохраняем ID и название выбранной подкатегории в состояние
        await state.update_data(
            category_id=selected_subcategory["id"],
            subcategory_name=selected_subcategory["name"]
        )
        
        # Получаем конфигурацию для ввода названия продукта
        product_name_config = get_state_config(SupplierCreationStates.waiting_product_name)
        
        # Отправляем сообщение с запросом названия продукта
        await message.answer(
            product_name_config["text"],
            reply_markup=product_name_config.get("markup")
        )
        
        # Устанавливаем состояние ввода названия продукта
        await state.set_state(SupplierCreationStates.waiting_product_name)
        
    except ValueError:
        # Если пользователь ввел не число
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
    
    # Сохраняем название продукта в состояние
    await state.update_data(product_name=product_name)
    
    # Показываем подтверждение данных
    await show_supplier_confirmation(message, state, bot)

@router.callback_query(SupplierCreationStates.confirm_supplier_creation, F.data == "confirm")
async def confirm_supplier_creation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение создания поставщика"""
    await callback.answer()
    
    # Получаем все данные из состояния
    state_data = await state.get_data()
    
    try:
        # Сохраняем поставщика в базу данных
        async with get_db_session() as session:
            db_service = DBService(session)
            
            supplier_id = await db_service.save_supplier(
                company_name=state_data.get("company_name"),
                product_name=state_data.get("product_name"),
                category_id=state_data.get("category_id"),
                created_by_id=state_data.get("user_id")
            )
            
            if not supplier_id:
                raise Exception("Ошибка при сохранении поставщика")
            
            # Удаляем клавиатуру у текущего сообщения
            await remove_keyboard_from_context(bot, callback)
            
            # Показываем успешное создание
            await callback.message.answer(
                f"Поставщик успешно создан!\n\n"
                f"ID: {supplier_id}\n"
                f"Компания: {state_data.get('company_name', '')}\n"
                f"Категория: {state_data.get('main_category', '')}\n"
                f"Подкатегория: {state_data.get('subcategory_name', '')}\n"
                f"Продукт/услуга: {state_data.get('product_name', '')}"
            )
            
            # Возвращаемся в меню поставщиков
            from app.config.action_config import get_action_config
            action_config = get_action_config("suppliers_list")
            
            await callback.message.answer(
                action_config.get("text", "Меню поставщиков:"),
                reply_markup=action_config.get("markup")
            )
            
            # Очищаем состояние
            await state.clear()
            
    except Exception as e:
        # Логируем ошибку
        logging.error(f"Error during supplier creation: {e}")
        
        # Удаляем клавиатуру у текущего сообщения
        await remove_keyboard_from_context(bot, callback)
        
        # Сообщаем пользователю об ошибке
        await callback.message.answer(
            "К сожалению, произошла ошибка при создании поставщика. Пожалуйста, попробуйте позже."
        )

# Вспомогательные функции
async def show_supplier_confirmation(message: Message, state: FSMContext, bot: Bot):
    """Показывает информацию для подтверждения создания поставщика"""
    # Получаем данные из состояния
    state_data = await state.get_data()
    
    # Создаем текст подтверждения
    confirmation_text = "Пожалуйста, проверьте введенные данные о поставщике:\n\n"
    confirmation_text += f"Компания: {state_data.get('company_name', '')}\n"
    confirmation_text += f"Категория: {state_data.get('main_category', '')}\n"
    confirmation_text += f"Подкатегория: {state_data.get('subcategory_name', '')}\n"
    confirmation_text += f"Продукт/услуга: {state_data.get('product_name', '')}\n"
    
    # Получаем конфигурацию для состояния подтверждения
    confirm_config = get_state_config(SupplierCreationStates.confirm_supplier_creation)
    
    # Устанавливаем состояние подтверждения
    await state.set_state(SupplierCreationStates.confirm_supplier_creation)
    
    # Отправляем сообщение с подтверждением
    await message.answer(
        confirmation_text,
        reply_markup=confirm_config.get("markup")
    )

def register_handlers(dp):
    dp.include_router(router) 