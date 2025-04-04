#!/bin/bash
# Скрипт инициализации PostgreSQL для локального использования на Ubuntu
# Имя: postgres_init.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}[+] Начинаем установку и настройку PostgreSQL для локального использования${NC}"

# Установка PostgreSQL и необходимых зависимостей
echo -e "${YELLOW}[*] Обновление списка пакетов...${NC}"
sudo apt-get update

echo -e "${YELLOW}[*] Установка PostgreSQL и необходимых зависимостей...${NC}"
sudo apt-get install -y postgresql postgresql-contrib libpq-dev

# Проверка успешности установки
if [ $? -ne 0 ]; then
    echo -e "${RED}[!] Ошибка при установке PostgreSQL${NC}"
    exit 1
fi

echo -e "${GREEN}[+] PostgreSQL успешно установлен${NC}"

# Создание пользователя и базы данных для приложения
echo -e "${YELLOW}[*] Создание пользователя и базы данных...${NC}"
DB_NAME="telegram_bot"
DB_USER="telegram_user"
DB_PASS=$(openssl rand -base64 12)  # Генерация случайного пароля

# Запуск и настройка службы PostgreSQL
echo -e "${YELLOW}[*] Запуск службы PostgreSQL...${NC}"
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание пользователя и БД
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# После создания базы данных и пользователя, добавить:
echo -e "${YELLOW}[*] Назначение расширенных прав пользователю...${NC}"
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TYPES TO $DB_USER;"

echo -e "${GREEN}[+] База данных и пользователь созданы${NC}"

# Настройка PostgreSQL для локального доступа с оптимизациями
echo -e "${YELLOW}[*] Оптимизация PostgreSQL для локального доступа...${NC}"

# Определяем путь к конфигурационному файлу PostgreSQL
PG_VERSION=$(psql --version | grep -oP '(?<=psql \(PostgreSQL\) )[0-9]+')
PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"

# Резервное копирование конфигурационных файлов
sudo cp $PG_CONF "${PG_CONF}.backup"
sudo cp $PG_HBA "${PG_HBA}.backup"

# Настройка postgresql.conf для локального доступа и оптимизации
sudo tee -a $PG_CONF > /dev/null << EOF

# Оптимизации для локального доступа - добавлено скриптом postgres_init.sh
listen_addresses = 'localhost'  # Слушать только локальные соединения
max_connections = 100           # Максимальное количество соединений
shared_buffers = 256MB          # Используем 25% от доступной памяти (настройте под свою систему)
effective_cache_size = 768MB    # Примерно 75% доступной памяти (настройте под свою систему)
work_mem = 16MB                 # Память для операций сортировки и хеширования
maintenance_work_mem = 64MB     # Память для задач обслуживания
wal_buffers = 8MB               # Буферы для журнала WAL
synchronous_commit = off        # Для максимальной производительности (осторожно в продакшене)
checkpoint_completion_target = 0.9  # Распределение записи контрольных точек
random_page_cost = 1.1          # Для быстрых дисков SSD
effective_io_concurrency = 200  # Для SSD дисков
autovacuum = on                 # Автоматическая очистка
log_min_duration_statement = 100  # Логирование долгих запросов

# Локальный доступ через Unix-сокеты
unix_socket_directories = '/var/run/postgresql'  # Путь к сокету
EOF

# Настройка pg_hba.conf для локального доступа
sudo tee $PG_HBA > /dev/null << EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Локальные соединения через Unix-сокеты
local   all             postgres                                peer
local   all             all                                     md5

# Локальные TCP/IP соединения
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5

# Разрешаем соединения для конкретного пользователя нашего приложения
local   $DB_NAME        $DB_USER                                md5
EOF

echo -e "${YELLOW}[*] Перезапуск PostgreSQL для применения настроек...${NC}"
sudo systemctl restart postgresql

# Проверка подключения
echo -e "${YELLOW}[*] Проверка подключения к базе данных...${NC}"
export PGPASSWORD="$DB_PASS"
if psql -h localhost -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}[+] Подключение к базе данных успешно${NC}"
else
    echo -e "${RED}[!] Ошибка подключения к базе данных${NC}"
    echo -e "${YELLOW}[*] Проверка через Unix-сокет...${NC}"
    if psql -h /var/run/postgresql -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}[+] Подключение через Unix-сокет успешно${NC}"
    else
        echo -e "${RED}[!] Ошибка подключения через Unix-сокет. Требуется ручная проверка.${NC}"
    fi
fi

# Обновление строки подключения в конфигурационном файле приложения
CONNECTION_STRING="postgresql+asyncpg://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
echo -e "${YELLOW}[*] Строка подключения для .env файла:${NC}"
echo -e "${GREEN}DATABASE_URL=$CONNECTION_STRING${NC}"

# Инструкции по подключению через Unix-сокет
SOCKET_STRING="postgresql+asyncpg://$DB_USER:$DB_PASS@/var/run/postgresql/$DB_NAME"
echo -e "${YELLOW}[*] Альтернативная строка подключения через Unix-сокет:${NC}"
echo -e "${GREEN}DATABASE_URL=$SOCKET_STRING${NC}"

echo -e "\n${GREEN}[+] Установка и настройка PostgreSQL завершена!${NC}"
echo -e "${YELLOW}[*] Сохраните данные для подключения:${NC}"
echo -e "${YELLOW}База данных: $DB_NAME${NC}"
echo -e "${YELLOW}Пользователь: $DB_USER${NC}"
echo -e "${YELLOW}Пароль: $DB_PASS${NC}"
echo -e "${YELLOW}Строка подключения: $CONNECTION_STRING${NC}"
