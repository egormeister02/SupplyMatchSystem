#!/bin/bash
# scripts/start_local.sh

# Установка переменных окружения
export APP_ENV="local"

# Фиксация функции очистки для выполнения при завершении
cleanup() {
    echo "Завершение работы и очистка..."
    
    # Останавливаем PostgreSQL
    echo "Останавливаем PostgreSQL..."
    sudo systemctl stop postgresql
    
    # Завершаем процесс ngrok, если он запущен
    if pgrep -x "ngrok" > /dev/null; then
        echo "Завершение ngrok..."
        pkill -f ngrok
    fi
    
    echo "Очистка выполнена!"
}

# Регистрируем функцию cleanup при завершении скрипта
trap cleanup EXIT

# Запускаем PostgreSQL, если он не запущен
if ! systemctl is-active --quiet postgresql; then
    echo "Запускаем PostgreSQL..."
    sudo systemctl start postgresql
    
    # Ждем пока PostgreSQL полностью запустится
    sleep 3
    
    # Проверка запуска PostgreSQL
    if systemctl is-active --quiet postgresql; then
        echo "PostgreSQL успешно запущен"
    else
        echo "Ошибка запуска PostgreSQL. Проверьте логи: sudo journalctl -u postgresql"
        exit 1
    fi
else
    echo "PostgreSQL уже запущен"
fi

# Проверка ngrok (если используется)
if grep -q "USE_NGROK=True" .env.local; then
    # Если ngrok уже запущен, получаем URL
    if pgrep -x "ngrok" > /dev/null; then
        echo "Ngrok уже запущен, получаем URL..."
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
        
        if [ -n "$NGROK_URL" ]; then
            echo "Найден URL ngrok: $NGROK_URL"
            # Обновляем в .env.local
            sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
        else
            echo "Не удалось получить URL ngrok. Запускаем новый экземпляр..."
            
            # Получаем токен из .env.local
            NGROK_TOKEN=$(grep NGROK_AUTH_TOKEN .env.local | cut -d'=' -f2)
            
            # Запускаем ngrok перенаправляя вывод в /dev/null
            ngrok http 8000 > /dev/null 2>&1 &
            
            # Увеличиваем время ожидания и добавляем проверку с повторами
            echo "Ожидаем запуск ngrok и получение туннеля..."
            MAX_ATTEMPTS=12
            ATTEMPT=1
            NGROK_URL=""

            while [ -z "$NGROK_URL" ] && [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
                echo "Попытка $ATTEMPT из $MAX_ATTEMPTS получить URL ngrok..."
                sleep 5
                NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
                ATTEMPT=$((ATTEMPT+1))
            done

            if [ -z "$NGROK_URL" ]; then
                echo "Не удалось получить URL ngrok после $MAX_ATTEMPTS попыток. Проверьте работу ngrok вручную."
                echo "Процесс ngrok будет завершен."
                pkill -f ngrok
                exit 1
            else
                echo "Настроен новый URL ngrok: $NGROK_URL"
                # Обновляем в .env.local
                sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
            fi
        fi
    else
        echo "Ngrok не запущен. Запускаем..."
        
        # Получаем токен из .env.local
        NGROK_TOKEN=$(grep NGROK_AUTH_TOKEN .env.local | cut -d'=' -f2)
        
        # Запускаем ngrok в фоновом режиме перенаправляя вывод
        ngrok http 8000 > /dev/null 2>&1 &
        
        # Увеличиваем время ожидания и добавляем проверку с повторами
        echo "Ожидаем запуск ngrok и получение туннеля..."
        MAX_ATTEMPTS=12
        ATTEMPT=1
        NGROK_URL=""

        while [ -z "$NGROK_URL" ] && [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
            echo "Попытка $ATTEMPT из $MAX_ATTEMPTS получить URL ngrok..."
            sleep 5
            NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
            ATTEMPT=$((ATTEMPT+1))
        done

        if [ -z "$NGROK_URL" ]; then
            echo "Не удалось получить URL ngrok после $MAX_ATTEMPTS попыток. Проверьте работу ngrok вручную."
            echo "Процесс ngrok будет завершен."
            pkill -f ngrok
            exit 1
        else
            echo "Настроен URL ngrok: $NGROK_URL"
            # Обновляем в .env.local
            sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
        fi
    fi
fi

# Запуск приложения
echo "Запуск бота..."
python -m app.main