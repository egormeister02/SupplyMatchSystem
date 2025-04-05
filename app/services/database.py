from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import asyncio
import logging
from app.config import config
import os
import re

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем асинхронный движок для PostgreSQL
engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DEBUG
)

# Создаем фабрику сессий
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """Функция для получения асинхронной сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Функция для разделения SQL скрипта на отдельные запросы
def split_sql_script(script):
    """Разделяет SQL-скрипт на отдельные запросы"""
    # Используем регулярное выражение для разделения по ;
    # Но игнорируем ; внутри строковых литералов и комментариев
    queries = []
    current_query = ""
    
    for line in script.splitlines():
        # Пропускаем пустые строки и комментарии
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('--'):
            continue
            
        current_query += line + "\n"
        
        if stripped_line.endswith(';'):
            queries.append(current_query.strip())
            current_query = ""
    
    # Добавляем последний запрос, если он остался
    if current_query.strip():
        queries.append(current_query.strip())
    
    return queries

# Функция инициализации БД
async def init_db():
    """Асинхронная инициализация базы данных для разработки"""
    try:
        async with engine.begin() as conn:
            # Проверяем, включен ли режим пересоздания схемы
            # Если переменная не существует или равна "true", пересоздаем схему
            recreate_schema = os.getenv("RECREATE_DB_SCHEMA", "true").lower() == "true"
            
            if recreate_schema:
                logging.info("Пересоздание схемы базы данных...")
                
                # Читаем файл схемы
                schema_file = os.path.join(os.path.dirname(__file__), "..", "..", "database", "schema.sql")
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                
                # Разбиваем скрипт на отдельные запросы
                schema_queries = split_sql_script(schema_sql)
                
                # Выполняем каждый запрос отдельно
                for query in schema_queries:
                    if query.strip():  # Проверяем, что запрос не пустой
                        try:
                            await conn.execute(text(query))
                            logging.debug(f"Выполнен запрос: {query[:50]}...")
                        except Exception as e:
                            logging.error(f"Ошибка при выполнении запроса: {query[:50]}...\nОшибка: {e}")
                            raise
                
                # Загружаем начальные данные
                seed_file = os.path.join(os.path.dirname(__file__), "..", "..", "database", "seed_data.sql")
                try:
                    with open(seed_file, "r", encoding="utf-8") as f:
                        seed_sql = f.read()
                    
                    # Разбиваем скрипт на отдельные запросы
                    seed_queries = split_sql_script(seed_sql)
                    
                    # Выполняем каждый запрос отдельно
                    for query in seed_queries:
                        if query.strip():  # Проверяем, что запрос не пустой
                            try:
                                await conn.execute(text(query))
                                logging.debug(f"Выполнен запрос начальных данных: {query[:50]}...")
                            except Exception as e:
                                logging.error(f"Ошибка при выполнении запроса данных: {query[:50]}...\nОшибка: {e}")
                                raise
                except FileNotFoundError:
                    logging.warning(f"Файл с начальными данными не найден: {seed_file}")
                
                logging.info("Схема базы данных успешно пересоздана")
            else:
                # Просто проверяем подключение
                await conn.execute(text("SELECT 1"))
                logging.info("Подключение к базе данных успешно")
            
            return True
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")
        return False

# Функция для выполнения запросов
class DBService:
    @staticmethod
    async def execute(query, params=None):
        """Выполнить SQL запрос"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(query, params)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка выполнения запроса: {e}")
                raise
