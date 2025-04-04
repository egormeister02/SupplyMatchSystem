from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import asyncio
import logging
from app.config import config
import os

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
                
                # Создаем всю схему сразу
                await conn.execute(text(schema_sql))
                
                # Загружаем начальные данные
                seed_file = os.path.join(os.path.dirname(__file__), "..", "..", "database", "seed_data.sql")
                with open(seed_file, "r", encoding="utf-8") as f:
                    seed_sql = f.read()
                
                # Вставляем начальные данные
                await conn.execute(text(seed_sql))
                
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
