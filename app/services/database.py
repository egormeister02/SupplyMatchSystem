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
    echo=True
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
            logger.info("RECREATE_DB_SCHEMA = True, начинаем инициализацию базы данных")
            
            # Get init directory path
            init_path = Path(__file__).parent.parent.parent / 'database' / 'init'
            
            # Execute initialization scripts in order
            for script_file in sorted(init_path.glob('*.sql')):
                logger.info(f"Executing initialization script: {script_file.name}")
                with open(script_file, 'r', encoding='utf-8') as f:
                    script = f.read()
                
                # Split script into individual queries
                queries = split_sql_script(script)
                
                # Execute each query separately
                for i, query in enumerate(queries):
                    if not query.strip():  # Skip empty queries
                        continue
                    try:
                        logger.info(f"Executing query {i+1} from {script_file.name}: {query[:100]}...")
                        await DBService.execute(query)
                        logger.info(f"Successfully executed query {i+1} from {script_file.name}")
                    except Exception as e:
                        logger.error(f"Error executing query {i+1} from {script_file.name}: {str(e)}")
                        logger.error(f"Problematic query: {query}")
                        logger.error(f"Exception type: {type(e).__name__}")
                        logger.error(f"Full exception: {repr(e)}")
                        # Continue with next query even if one fails
                        continue
            
            logger.info("Database initialization completed")
        else:
            logger.info("RECREATE_DB_SCHEMA = False, пропускаем инициализацию базы данных")
            
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
    