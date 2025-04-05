from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import asyncio
import logging
from app.config import config
import os
import re
from contextlib import asynccontextmanager

# Base class for models
Base = declarative_base()

# Create async engine for PostgreSQL
engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DEBUG
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
    """Splits SQL script into separate queries"""
    # Use regex to split by semicolon
    # But ignore semicolons inside string literals and comments
    queries = []
    current_query = ""
    
    for line in script.splitlines():
        # Skip empty lines and comments
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('--'):
            continue
            
        current_query += line + "\n"
        
        if stripped_line.endswith(';'):
            queries.append(current_query.strip())
            current_query = ""
    
    # Add the last query if it exists
    if current_query.strip():
        queries.append(current_query.strip())
    
    return queries

# Database initialization function
async def init_db():
    """Async database initialization for development"""
    try:
        async with engine.begin() as conn:
            # Check if schema recreation mode is enabled
            # If the variable doesn't exist or equals "true", recreate schema
            recreate_schema = os.getenv("RECREATE_DB_SCHEMA", "true").lower() == "true"
            
            if recreate_schema:
                logging.info("Recreating database schema...")
                
                # Read schema file
                schema_file = os.path.join(os.path.dirname(__file__), "..", "..", "database", "schema.sql")
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                
                # Split script into separate queries
                schema_queries = split_sql_script(schema_sql)
                
                # Execute each query separately
                for query in schema_queries:
                    if query.strip():  # Check that query is not empty
                        try:
                            await conn.execute(text(query))
                            logging.debug(f"Executed query: {query[:50]}...")
                        except Exception as e:
                            logging.error(f"Error executing query: {query[:50]}...\nError: {e}")
                            raise
                
                # Load initial data
                seed_file = os.path.join(os.path.dirname(__file__), "..", "..", "database", "seed_data.sql")
                try:
                    with open(seed_file, "r", encoding="utf-8") as f:
                        seed_sql = f.read()
                    
                    # Split script into separate queries
                    seed_queries = split_sql_script(seed_sql)
                    
                    # Execute each query separately
                    for query in seed_queries:
                        if query.strip():  # Check that query is not empty
                            try:
                                await conn.execute(text(query))
                                logging.debug(f"Executed seed data query: {query[:50]}...")
                            except Exception as e:
                                logging.error(f"Error executing seed data query: {query[:50]}...\nError: {e}")
                                raise
                except FileNotFoundError:
                    logging.warning(f"Seed data file not found: {seed_file}")
                
                logging.info("Database schema successfully recreated")
            else:
                # Just check connection
                await conn.execute(text("SELECT 1"))
                logging.info("Database connection successful")
            
            return True
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        return False

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
    async def execute(query, params=None):
        """Execute SQL query with a new session (static method)"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(text(query), params)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logging.error(f"Query execution error: {e}")
                raise
    
    async def check_user_exists(self, user_id: int) -> bool:
        """Check if user exists in database by Telegram ID"""
        query = "SELECT 1 FROM users WHERE tg_id = :user_id LIMIT 1"
        result = await self.execute_query(query, {"user_id": user_id})
        return result.scalar() is not None
    
    async def save_user(
        self, 
        user_id: int, 
        username: str, 
        first_name: str, 
        last_name: str, 
        email: str = None, 
        phone: str = None
    ) -> bool:
        """
        Save user to database. If user exists, update their information.
        
        Args:
            user_id (int): Telegram user ID
            username (str): Telegram username (can be None)
            first_name (str): User's first name
            last_name (str): User's last name
            email (str, optional): User's email address
            phone (str, optional): User's phone number
            
        Returns:
            bool: True if operation was successful
        """
        query = """
            INSERT INTO users (tg_id, username, first_name, last_name, email, phone, created_at)
            VALUES (:user_id, :username, :first_name, :last_name, :email, :phone, NOW())
            ON CONFLICT (tg_id) DO UPDATE
            SET username = :username, 
                first_name = :first_name, 
                last_name = :last_name,
                email = COALESCE(:email, users.email),
                phone = COALESCE(:phone, users.phone)
        """
        params = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone
        }
        
        try:
            await self.execute_query(query, params)
            await self.commit()
            logging.info(f"User saved: {user_id}, {username}, email: {email or 'NULL'}, phone: {phone or 'NULL'}")
            return True
        except Exception as e:
            await self.rollback()
            logging.error(f"Error saving user: {e}")
            return False
