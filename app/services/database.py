from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import asyncio
import logging
from app.config import config
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
# Base class for models
Base = declarative_base()

# Create async engine for PostgreSQL
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

@asynccontextmanager
async def get_db_session():
    """Async context manager for database sessions"""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

# Function to split SQL script into separate queries
def split_sql_script(script):
    """Splits SQL script into separate queries handling dollar-quoted strings in PostgreSQL"""
    queries = []
    current_query = ""
    in_dollar_quote = False
    dollar_quote_tag = ""
    
    # Split by semicolons that are not inside dollar quotes
    parts = script.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Check for dollar quotes
        if '$$' in part:
            if not in_dollar_quote:
                in_dollar_quote = True
                current_query = part
            else:
                current_query += ';' + part
                in_dollar_quote = False
                queries.append(current_query)
                current_query = ""
        else:
            if in_dollar_quote:
                current_query += ';' + part
            else:
                queries.append(part)
    
    # Add the last query if it exists and wasn't already added
    if current_query.strip():
        queries.append(current_query.strip())
    
    return queries

# Database initialization function
async def init_db():
    """Initialize database with schema"""
    try:
        # Проверяем флаг RECREATE_DB_SCHEMA в конфигурации
        if str(config.RECREATE_DB_SCHEMA).lower() == 'true':
            logger.info("Инициализация базы данных (RECREATE_DB_SCHEMA = True)")
            
            # Get init directory path
            init_path = Path(__file__).parent.parent.parent / 'database' / 'init'
            
            # Execute initialization scripts in order
            for script_file in sorted(init_path.glob('*.sql')):
                logger.debug(f"Executing initialization script: {script_file.name}")
                with open(script_file, 'r', encoding='utf-8') as f:
                    script = f.read()
                
                # Split script into individual queries
                queries = split_sql_script(script)
                
                # Execute each query separately
                for i, query in enumerate(queries):
                    if not query.strip():  # Skip empty queries
                        continue
                    try:
                        logger.debug(f"Executing query {i+1} from {script_file.name}: {query[:100]}...")
                        await DBService.execute(query)
                        logger.debug(f"Successfully executed query {i+1} from {script_file.name}")
                    except Exception as e:
                        logger.error(f"Error executing query {i+1} from {script_file.name}: {str(e)}")
                        logger.error(f"Problematic query: {query}")
                        logger.error(f"Exception type: {type(e).__name__}")
                        logger.error(f"Full exception: {repr(e)}")
                        # Continue with next query even if one fails
                        continue
            
            logger.info("Инициализация базы данных завершена")
        else:
            logger.debug("RECREATE_DB_SCHEMA = False, пропускаем инициализацию базы данных")
            
        return True  # Return True to indicate success
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full exception: {repr(e)}")
        return False  # Return False to indicate failure

# Class for database operations
class DBService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def execute_query(self, query, params=None):
        """Execute SQL query in current session"""
        try:
            result = await self.session.execute(text(query), params)
            return result
        except Exception as e:
            logging.error(f"Query execution error: {e}")
            raise
            
    async def commit(self):
        await self.session.commit()
        
    async def rollback(self):
        await self.session.rollback()
            
    @staticmethod
    async def execute(query: str, params: dict = None) -> None:
        """Execute a query without returning results"""
        try:
            async with engine.begin() as conn:
                if params:
                    await conn.execute(text(query), params)
                else:
                    await conn.execute(text(query))
        except Exception as e:
            logger.error(f"Error executing query: {query[:100]}...")
            logger.error(f"Error details: {str(e)}")
            raise
    
    @staticmethod
    async def fetch_data(query: str, params: dict = None):
        """
        Статический метод для выполнения запросов только на чтение.
        Не требует создания сессии и не держит соединение открытым.
        
        Args:
            query (str): SQL запрос
            params (dict, optional): Параметры запроса
            
        Returns:
            list: Список словарей с результатами запроса или None если ничего не найдено
        """
        try:
            async with engine.connect() as conn:
                if params:
                    result = await conn.execute(text(query), params)
                else:
                    result = await conn.execute(text(query))
                    
                return [dict(row) for row in result.mappings()]
        except Exception as e:
            logger.error(f"Error executing read query: {query[:100]}...")
            logger.error(f"Error details: {str(e)}")
            raise
    
    @staticmethod
    async def fetch_one(query: str, params: dict = None):
        """
        Статический метод для выполнения запросов только на чтение и получения одной записи.
        
        Args:
            query (str): SQL запрос
            params (dict, optional): Параметры запроса
            
        Returns:
            dict: Словарь с результатом запроса или None если ничего не найдено
        """
        try:
            async with engine.connect() as conn:
                if params:
                    result = await conn.execute(text(query), params)
                else:
                    result = await conn.execute(text(query))
                    
                row = result.mappings().first()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error executing read query: {query[:100]}...")
            logger.error(f"Error details: {str(e)}")
            raise
    
    # Методы, связанные с topics и topic_id, а также id в users_jokes, удалены
    # Оставляю только методы для работы с существующими таблицами и полями
    
    @staticmethod
    async def create_topic(topic: str, session: AsyncSession = None) -> int:
        """
        Создает новую тему (topic) и возвращает её id. Если тема уже есть — возвращает её id.
        """
        query = "INSERT INTO topics (topic) VALUES (:topic) RETURNING id"
        select_query = "SELECT id FROM topics WHERE topic = :topic"
        try:
            if session is not None:
                # Сначала пробуем найти существующий топик
                result = await session.execute(text(select_query), {"topic": topic})
                row = result.mappings().first()
                if row and "id" in row:
                    logger.debug(f"Topic already exists with ID: {row['id']}")
                    return int(row["id"])
                # Если не найден — создаём новый
                result = await session.execute(text(query), {"topic": topic})
                row = result.mappings().first()
                if row and "id" in row:
                    logger.debug(f"Created topic with ID: {row['id']}")
                    return int(row["id"])
                raise ValueError("Failed to create or find topic - no ID returned")
            else:
                # Старый режим — отдельная сессия
                async with engine.begin() as conn:
                    # Сначала пробуем найти существующий топик
                    result = await conn.execute(text(select_query), {"topic": topic})
                    row = result.mappings().first()
                    if row and "id" in row:
                        logger.debug(f"Topic already exists with ID: {row['id']}")
                        return int(row["id"])
                    # Если не найден — создаём новый
                    result = await conn.execute(text(query), {"topic": topic})
                    row = result.mappings().first()
                    if row and "id" in row:
                        logger.debug(f"Created topic with ID: {row['id']}")
                        return int(row["id"])
                    raise ValueError("Failed to create or find topic - no ID returned")
        except Exception as e:
            logger.error(f"Error creating topic: {str(e)}")
            raise
    
    @staticmethod
    async def create_joke(topic_id: int, text_joke: str, session: AsyncSession = None) -> int:
        """
        Создает новый анекдот для темы и возвращает его id.
        """
        query = "INSERT INTO jokes (topic_id, joke) VALUES (:topic_id, :joke) RETURNING id"
        try:
            if session is not None:
                result = await session.execute(text(query), {"topic_id": topic_id, "joke": text_joke})
                row = result.mappings().first()
                if row and "id" in row:
                    logger.debug(f"Created joke with ID: {row['id']} for topic_id: {topic_id}")
                    return int(row["id"]) 
                else:
                    raise ValueError("Failed to create joke - no ID returned")
            else:
                async with engine.begin() as conn:
                    result = await conn.execute(text(query), {"topic_id": topic_id, "joke": text_joke})
                    row = result.mappings().first()
                    if row and "id" in row:
                        logger.debug(f"Created joke with ID: {row['id']} for topic_id: {topic_id}")
                        return int(row["id"]) 
                    else:
                        raise ValueError("Failed to create joke - no ID returned")
        except Exception as e:
            logger.error(f"Error creating joke: {str(e)}")
            raise
    
    @staticmethod
    async def get_jokes_by_topic_id(topic_id: int) -> list:
        """
        Получает все анекдоты для определенной темы.
        """
        try:
            query = """
                SELECT id, joke, created_at FROM jokes WHERE topic_id = :topic_id ORDER BY id
            """
            return await DBService.fetch_data(query, {"topic_id": topic_id})
        except Exception as e:
            logger.error(f"Error getting jokes by topic ID: {str(e)}")
            raise
    
    @staticmethod
    async def get_random_joke_for_user(user_id: int) -> dict:
        """
        Получает случайный анекдот для пользователя, который он еще не слышал (по views).
        """
        try:
            query = """
                SELECT j.id, j.joke, t.topic
                FROM user_unheard_jokes uuj
                JOIN jokes j ON j.id = uuj.joke_id
                JOIN topics t ON t.id = j.topic_id
                WHERE uuj.tg_id = :user_id
                ORDER BY RANDOM()
                LIMIT 1
            """
            return await DBService.fetch_one(query, {"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting random joke for user: {str(e)}")
            raise
    
    @staticmethod
    async def get_random_unseen_joke_for_user(user_id: int) -> dict:
        """
        Возвращает случайный анекдот, который пользователь ещё не видел (нет записи в users_jokes)
        """
        try:
            query = """
                SELECT j.id, j.joke, t.topic
                FROM jokes j
                JOIN topics t ON t.id = j.topic_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM users_jokes uj WHERE uj.user_id = :user_id AND uj.joke_id = j.id
                )
                ORDER BY RANDOM()
                LIMIT 1
            """
            return await DBService.fetch_one(query, {"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting random unseen joke for user: {str(e)}")
            raise
    
    @staticmethod
    async def record_user_joke_interaction(user_id: int, joke_id: int, reaction: str = "skip") -> int:
        """
        Записывает взаимодействие пользователя с анекдотом и возвращает users_jokes.id.
        """
        try:
            # Сразу пытаемся получить существующую запись и её id
            check_query = """
                SELECT id FROM users_jokes WHERE user_id = :user_id AND joke_id = :joke_id
            """
            existing = await DBService.fetch_one(check_query, {
                "user_id": user_id,
                "joke_id": joke_id
            })
            if existing and "id" in existing:
                # Обновляем существующую запись и возвращаем её id
                update_query = """
                    UPDATE users_jokes SET reaction = :reaction, created_at = NOW()
                    WHERE id = :id
                """
                await DBService.execute(update_query, {
                    "id": existing["id"],
                    "reaction": reaction
                })
                logger.debug(f"Updated user {user_id} reaction to joke {joke_id}: {reaction}")
                return int(existing["id"]) 
            else:
                # Создаем новую запись и сразу возвращаем её id
                insert_query = """
                    INSERT INTO users_jokes (user_id, joke_id, reaction)
                    VALUES (:user_id, :joke_id, :reaction)
                    RETURNING id
                """
                async with engine.begin() as conn:
                    result = await conn.execute(text(insert_query), {
                        "user_id": user_id,
                        "joke_id": joke_id,
                        "reaction": reaction
                    })
                    row = result.mappings().first()
                    if row and "id" in row:
                        logger.debug(f"Recorded user {user_id} reaction to joke {joke_id}: {reaction} with id {row['id']}")
                        return int(row["id"]) 
                    raise ValueError("Failed to insert users_jokes - no ID returned")
        except Exception as e:
            logger.error(f"Error recording user joke interaction: {str(e)}")
            raise

    @staticmethod
    async def update_users_jokes_reaction_by_id(users_jokes_id: int, reaction: str) -> None:
        """
        Обновляет реакцию в таблице users_jokes по её первичному ключу.
        """
        query = """
            UPDATE users_jokes 
            SET reaction = :reaction 
            WHERE id = :users_jokes_id
        """
        await DBService.execute(query, {"reaction": reaction, "users_jokes_id": users_jokes_id})

    @staticmethod
    async def get_joke_text_by_users_jokes_id(users_jokes_id: int, user_id: int) -> str | None:
        """
        Возвращает текст анекдота по users_jokes.id и user_id. Возвращает None, если не найдено.
        """
        query = """
            SELECT j.joke
            FROM users_jokes uj
            JOIN jokes j ON j.id = uj.joke_id 
            JOIN topics t ON t.id = j.topic_id 
            WHERE uj.id = :users_jokes_id AND uj.user_id = :user_id
        """
        row = await DBService.fetch_one(query, {"users_jokes_id": users_jokes_id, "user_id": user_id})
        return row["joke"] if row and "joke" in row else None
    
    @staticmethod
    async def get_jokes_and_reactions_by_topic_id(topic_id: int) -> list:
        """
        Возвращает все анекдоты по теме и количество like/dislike для каждого.
        [{"id": ..., "joke": ..., "likes": ..., "dislikes": ...}, ...]
        """
        try:
            query = """
                SELECT j.id, j.joke,
                    COALESCE(SUM(CASE WHEN uj.reaction = 'like' THEN 1 ELSE 0 END), 0) as likes,
                    COALESCE(SUM(CASE WHEN uj.reaction = 'dislike' THEN 1 ELSE 0 END), 0) as dislikes
                FROM jokes j
                LEFT JOIN users_jokes uj ON uj.joke_id = j.id
                WHERE j.topic_id = :topic_id
                GROUP BY j.id, j.joke
                ORDER BY j.id
            """
            return await DBService.fetch_data(query, {"topic_id": topic_id})
        except Exception as e:
            logger.error(f"Error getting jokes and reactions by topic ID: {str(e)}")
            raise
    