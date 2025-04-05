#!/bin/bash
# scripts/start_local.sh

# Set environment variables
export APP_ENV="local"

# Define cleanup function to execute on exit
cleanup() {
    echo "Завершение работы и очистка..."
    
    # Stop PostgreSQL
    #echo "Останавливаем PostgreSQL..."
    #sudo systemctl stop postgresql
    
    echo "Очистка выполнена!"
}

# Register cleanup function for script termination
trap cleanup EXIT

# Start PostgreSQL if not running
if ! systemctl is-active --quiet postgresql; then
    echo "Запускаем PostgreSQL..."
    sudo systemctl start postgresql
    
    # Wait for PostgreSQL to fully start
    sleep 3
    
    # Check PostgreSQL status
    if systemctl is-active --quiet postgresql; then
        echo "PostgreSQL успешно запущен"
    else
        echo "Ошибка запуска PostgreSQL. Проверьте логи: sudo journalctl -u postgresql"
        exit 1
    fi
else
    echo "PostgreSQL уже запущен"
fi

# Check ngrok (if used)
if grep -q "USE_NGROK=True" .env.local; then
    # If ngrok is already running, get URL
    if pgrep -x "ngrok" > /dev/null; then
        echo "Ngrok уже запущен, получаем URL..."
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
        
        if [ -n "$NGROK_URL" ]; then
            echo "Найден URL ngrok: $NGROK_URL"
            # Update in .env.local
            sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
        else
            echo "Не удалось получить URL ngrok. Запускаем новый экземпляр..."
            
            # Get token from .env.local
            NGROK_TOKEN=$(grep NGROK_AUTH_TOKEN .env.local | cut -d'=' -f2)
            
            # Start ngrok redirecting output to /dev/null
            ngrok http 8000 > /dev/null 2>&1 &
            
            # Increase wait time and add retry checks
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
                # Update in .env.local
                sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
            fi
        fi
    else
        echo "Ngrok не запущен. Запускаем..."
        
        # Get token from .env.local
        NGROK_TOKEN=$(grep NGROK_AUTH_TOKEN .env.local | cut -d'=' -f2)
        
        # Start ngrok in background redirecting output
        ngrok http 8000 > /dev/null 2>&1 &
        
        # Increase wait time and add retry checks
        echo "Ожидаем запуск ngrok и получение туннеля..."
        MAX_ATTEMPTS=12
        ATTEMPT=1
        NGROK_URL=""

        while [ -z "$NGROK_URL" ] && [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
            echo "Попытка $ATTEMPT из $MAX_ATTEMPTS получить URL ngrok..."
            sleep 1
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
            # Update in .env.local
            sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=$NGROK_URL|g" .env.local
        fi
    fi
fi

# Start application
echo "Запуск бота..."
python -m app.main