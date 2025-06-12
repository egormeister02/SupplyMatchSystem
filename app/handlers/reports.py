from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.services.report_requests import ReportRequests
from app.services.report_tables import SupplierRequestsReportXLSX, SeekerRequestsReportXLSX, SuppliersActivityReportXLSX, ReviewsReportXLSX
from app.services.graph import generate_requests_graph, generate_status_pie_charts
from app.config.action_config import get_action_config

import logging

router = Router()

class GraphDays(StatesGroup):
    waiting_for_days = State()

class PieGraphDays(StatesGroup):
    waiting_for_pie_days = State()

class Top10CategoriesDays(StatesGroup):
    waiting_for_days = State()

class Top10SuppliersDays(StatesGroup):
    waiting_for_days = State()

@router.callback_query(F.data == "report_table_suppliers")
async def ask_report_period(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    # Получаем конфиг для выбора периода
    action_config = get_action_config("report_table_suppliers_period")
    if not action_config:
        await callback.message.answer("Ошибка конфигурации отчёта.")
        return
    await callback.message.answer(
        action_config["text"],
        reply_markup=action_config.get("markup")
    )

@router.callback_query(F.data.startswith("report_table_suppliers_period:"))
async def handle_report_table_suppliers_period(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        try:
            await callback.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
        period = callback.data.split(":")[1]
        months = None if period == "all" else int(period)
        # Получаем данные для отчёта с учётом периода
        data = await ReportRequests.get_supplier_requests_report(months=months)
        if not data:
            # Показываем меню выбора отчёта из action_config
            action_config = get_action_config("reports")
            await callback.message.answer("Нет данных для отчёта за выбранный период.", reply_markup=action_config.get("markup"))
            return
        # Генерируем xlsx-файл через класс
        report = SupplierRequestsReportXLSX(data)
        file_path = await report.generate()
        # Отправляем файл пользователю
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(file_path),
            caption=f"Отчёт по заявкам на поставщиков за {period if period != 'all' else 'всё время'}"
        )
        # После отправки файла показываем меню выбора отчёта из action_config
        action_config = get_action_config("reports")
        await callback.message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup")
        )
    except Exception as e:
        logging.error(f"Ошибка при формировании отчёта: {e}")
        action_config = get_action_config("reports")
        await callback.message.answer("Произошла ошибка при формировании отчёта. Попробуйте позже.", reply_markup=action_config.get("markup"))

# Новый обработчик для "Заявки искателей"
@router.callback_query(F.data == "report_table_seekers")
async def ask_report_period_seekers(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_table_seekers_period")
    if not action_config:
        await callback.message.answer("Ошибка конфигурации отчёта.")
        return
    await callback.message.answer(
        action_config["text"],
        reply_markup=action_config.get("markup")
    )

@router.callback_query(F.data.startswith("report_table_seekers_period:"))
async def handle_report_table_seekers_period(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        try:
            await callback.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
        period = callback.data.split(":")[1]
        months = None if period == "all" else int(period)
        data = await ReportRequests.get_seeker_requests_report(months=months)
        if not data:
            action_config = get_action_config("reports")
            await callback.message.answer("Нет данных для отчёта за выбранный период.", reply_markup=action_config.get("markup"))
            return
        report = SeekerRequestsReportXLSX(data)
        file_path = await report.generate()
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(file_path),
            caption=f"Отчёт по заявкам искателей за {period if period != 'all' else 'всё время'}"
        )
        action_config = get_action_config("reports")
        await callback.message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup")
        )
    except Exception as e:
        logging.error(f"Ошибка при формировании отчёта: {e}")
        action_config = get_action_config("reports")
        await callback.message.answer("Произошла ошибка при формировании отчёта. Попробуйте позже.", reply_markup=action_config.get("markup"))

@router.callback_query(F.data == "report_table_activity")
async def ask_report_period_activity(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_table_activity_period")
    if not action_config:
        await callback.message.answer("Ошибка конфигурации отчёта.")
        return
    await callback.message.answer(
        action_config["text"],
        reply_markup=action_config.get("markup")
    )

@router.callback_query(F.data.startswith("report_table_activity_period:"))
async def handle_report_table_activity_period(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        try:
            await callback.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
        period = callback.data.split(":")[1]
        months = None if period == "all" else int(period)
        data = await ReportRequests.get_suppliers_activity_report(months=months)
        if not data:
            action_config = get_action_config("reports")
            await callback.message.answer("Нет данных для отчёта за выбранный период.", reply_markup=action_config.get("markup"))
            return
        report = SuppliersActivityReportXLSX(data)
        file_path = await report.generate()
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(file_path),
            caption=f"Отчёт по активности поставщиков за {period if period != 'all' else 'всё время'}"
        )
        action_config = get_action_config("reports")
        await callback.message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup")
        )
    except Exception as e:
        logging.error(f"Ошибка при формировании отчёта: {e}")
        action_config = get_action_config("reports")
        await callback.message.answer("Произошла ошибка при формировании отчёта. Попробуйте позже.", reply_markup=action_config.get("markup"))

@router.callback_query(F.data == "report_table_reviews")
async def ask_report_period_reviews(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_table_reviews_period")
    if not action_config:
        await callback.message.answer("Ошибка конфигурации отчёта.")
        return
    await callback.message.answer(
        action_config["text"],
        reply_markup=action_config.get("markup")
    )

@router.callback_query(F.data.startswith("report_table_reviews_period:"))
async def handle_report_table_reviews_period(callback: CallbackQuery, bot: Bot, state):
    await callback.answer()
    try:
        try:
            await callback.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
        period = callback.data.split(":")[1]
        months = None if period == "all" else int(period)
        data = await ReportRequests.get_reviews_report(months=months)
        if not data:
            action_config = get_action_config("reports")
            await callback.message.answer("Нет данных для отчёта за выбранный период.", reply_markup=action_config.get("markup"))
            return
        report = ReviewsReportXLSX(data)
        file_path = await report.generate()
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(file_path),
            caption=f"Отчёт по отзывам за {period if period != 'all' else 'всё время'}"
        )
        action_config = get_action_config("reports")
        await callback.message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup")
        )
    except Exception as e:
        logging.error(f"Ошибка при формировании отчёта: {e}")
        action_config = get_action_config("reports")
        await callback.message.answer("Произошла ошибка при формировании отчёта. Попробуйте позже.", reply_markup=action_config.get("markup"))

@router.callback_query(F.data == "report_graph_by_days")
async def ask_graph_days(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    
    await callback.message.answer(
        "Введите количество дней для отображения графика (от 1 до 90):"
    )
    await state.set_state(GraphDays.waiting_for_days)

@router.message(GraphDays.waiting_for_days)
async def handle_graph_days(message: Message, state: FSMContext, bot: Bot):
    try:
        logging.info(f"Получено сообщение: {message.text}")
        days = int(message.text)
        logging.info(f"Преобразованное число дней: {days}")
        
        if not 1 <= days <= 90:
            logging.warning(f"Некорректное количество дней: {days}")
            await message.answer("Пожалуйста, введите число от 1 до 90.")
            return
        
        # Get data for the graph
        logging.info(f"Запрашиваем данные за {days} дней")
        data = await ReportRequests.get_requests_by_days(days)
        logging.info(f"Получены данные: {data}")
        
        if not data["supplier_requests"] and not data["seeker_requests"]:
            action_config = get_action_config("reports")
            await message.answer(
                "Нет данных для отображения за выбранный период.",
                reply_markup=action_config.get("markup")
            )
            return
        
        # Generate graph
        logging.info("Генерируем график")
        file_path = generate_requests_graph(data, days)
        logging.info(f"График сохранен в {file_path}")
        
        # Send the graph
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(file_path),
            caption=f"График заявок за последние {days} дней"
        )
        
        # Show reports menu
        action_config = get_action_config("reports")
        await message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup")
        )
        
    except ValueError as e:
        logging.error(f"Ошибка преобразования числа: {e}")
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logging.error(f"Ошибка при формировании графика: {e}")
        action_config = get_action_config("reports")
        await message.answer(
            "Произошла ошибка при формировании графика. Попробуйте позже.",
            reply_markup=action_config.get("markup")
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "report_graph_pie")
async def ask_pie_graph_days(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_graph_pie")
    await callback.message.answer(
        action_config["text"] if action_config else "Введите количество дней для отображения круговой диаграммы (от 1 до 90):"
    )
    await state.set_state(PieGraphDays.waiting_for_pie_days)

@router.message(PieGraphDays.waiting_for_pie_days)
async def handle_pie_graph_days(message: Message, state: FSMContext, bot: Bot):
    try:
        logging.info(f"Получено сообщение для pie: {message.text}")
        days = int(message.text)
        if days < 0:
            await message.answer("Пожалуйста, введите неотрицательное число (0 — всё время).")
            return
        # Получаем данные для круговой диаграммы
        data = await ReportRequests.get_requests_status_pie_data(days if days > 0 else None)
        if not data or (not data['suppliers'] and not data['seekers']):
            action_config = get_action_config("reports")
            await message.answer(
                "Нет данных для отображения за выбранный период.",
                reply_markup=action_config.get("markup") if action_config else None
            )
            return
        # Генерируем круговые диаграммы
        file_path = generate_status_pie_charts(data, days if days > 0 else None)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(file_path),
            caption=f"Круговые диаграммы статусов заявок за {'всё время' if days == 0 else f'{days} дней'}"
        )
        action_config = get_action_config("reports")
        await message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup") if action_config else None
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logging.error(f"Ошибка при формировании круговой диаграммы: {e}")
        action_config = get_action_config("reports")
        await message.answer(
            "Произошла ошибка при формировании диаграммы. Попробуйте позже.",
            reply_markup=action_config.get("markup") if action_config else None
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "report_graph_top10")
async def ask_top10_categories_days(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_graph_top10")
    await callback.message.answer(
        action_config["text"] if action_config else "Введите количество дней для топ-10 категорий (от 1 до 90, либо 0 для всего времени):"
    )
    await state.set_state(Top10CategoriesDays.waiting_for_days)

@router.message(Top10CategoriesDays.waiting_for_days)
async def handle_top10_categories_days(message: Message, state: FSMContext, bot: Bot):
    try:
        days = int(message.text)
        if days < 0:
            await message.answer("Пожалуйста, введите неотрицательное число (0 — всё время).")
            return
        data = await ReportRequests.get_top10_categories(days if days > 0 else None)
        if not data:
            action_config = get_action_config("reports")
            await message.answer(
                "Нет данных для отображения за выбранный период.",
                reply_markup=action_config.get("markup") if action_config else None
            )
            return
        from app.services.graph import generate_top10_categories_bar
        file_path = generate_top10_categories_bar(data, days if days > 0 else None)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(file_path),
            caption=f"Топ-10 категорий по заявкам за {'всё время' if days == 0 else f'{days} дней'}"
        )
        action_config = get_action_config("reports")
        await message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup") if action_config else None
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logging.error(f"Ошибка при формировании графика топ-10 категорий: {e}")
        action_config = get_action_config("reports")
        await message.answer(
            "Произошла ошибка при формировании графика. Попробуйте позже.",
            reply_markup=action_config.get("markup") if action_config else None
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "report_graph_activity")
async def ask_top10_suppliers_days(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")
    action_config = get_action_config("report_graph_activity")
    await callback.message.answer(
        action_config["text"] if action_config else "Введите количество дней для топ-10 активных поставщиков (от 1 до 90, либо 0 для всего времени):"
    )
    await state.set_state(Top10SuppliersDays.waiting_for_days)

@router.message(Top10SuppliersDays.waiting_for_days)
async def handle_top10_suppliers_days(message: Message, state: FSMContext, bot: Bot):
    try:
        days = int(message.text)
        if days < 0:
            await message.answer("Пожалуйста, введите неотрицательное число (0 — всё время).")
            return
        data = await ReportRequests.get_top10_suppliers_by_activity(days if days > 0 else None)
        if not data:
            action_config = get_action_config("reports")
            await message.answer(
                "Нет данных для отображения за выбранный период.",
                reply_markup=action_config.get("markup") if action_config else None
            )
            return
        from app.services.graph import generate_top10_suppliers_bar
        file_path = generate_top10_suppliers_bar(data, days if days > 0 else None)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(file_path),
            caption=f"Топ-10 активных поставщиков за {'всё время' if days == 0 else f'{days} дней'}"
        )
        action_config = get_action_config("reports")
        await message.answer(
            action_config["text"],
            reply_markup=action_config.get("markup") if action_config else None
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logging.error(f"Ошибка при формировании графика топ-10 поставщиков: {e}")
        action_config = get_action_config("reports")
        await message.answer(
            "Произошла ошибка при формировании графика. Попробуйте позже.",
            reply_markup=action_config.get("markup") if action_config else None
        )
    finally:
        await state.clear()

def register_handlers(dp):
    """Register file handlers with dispatcher"""
    dp.include_router(router) 