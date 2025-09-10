#!/usr/bin/env bash
set -e

# 1. Установить зависимости (PyInstaller)
pip install pyinstaller

# 2. Перейти в папку app
cd "app"

# 3. Собрать исполняемый файл
# --hidden-import нужны для aiogram/quart/sqlalchemy, если PyInstaller не находит их сам
pyinstaller \
  --name joke_bot \
  --onefile \
  --paths=. \
  --hidden-import=aiogram \
  --hidden-import=quart \
  --hidden-import=sqlalchemy.ext.asyncio \
  --hidden-import=app.handlers.base \
  --hidden-import=app.services.deepseek \
  --hidden-import=app.services.database \
  --hidden-import=app.utils.message_utils \
  --hidden-import=app.states.states \
  main.py

echo "Сборка завершена. Файл dist/joke_bot готов."