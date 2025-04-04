#!/bin/bash
# scripts/start_prod.sh

# Установка переменных окружения
export APP_ENV="production"

# Запуск приложения на сервере
python -m app.main
