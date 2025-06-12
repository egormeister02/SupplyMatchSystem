from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from app.services.report_requests import ReportRequests
from app.services.report_tables import create_supplier_requests_report_xlsx
from app.config.action_config import get_action_config

import logging

router = Router()


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
        # Генерируем xlsx-файл
        file_path = await create_supplier_requests_report_xlsx(data)
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

def register_handlers(dp):
    """Register file handlers with dispatcher"""
    dp.include_router(router) 