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
    
    @staticmethod
    async def check_user_exists_static(user_id: int) -> bool:
        """
        Статический метод для проверки существования пользователя по ID.
        Не требует создания сессии.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            bool: True если пользователь существует, иначе False
        """
        query = "SELECT 1 FROM users WHERE tg_id = :user_id LIMIT 1"
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(query), {"user_id": user_id})
                return result.scalar() is not None
        except Exception as e:
            logger.error(f"Error checking if user exists: {str(e)}")
            return False
    
    @staticmethod
    async def get_main_categories_static():
        """
        Статический метод для получения списка основных категорий.
        Не требует создания сессии.
        
        Returns:
            list: Список словарей с категориями
        """
        query = """
            SELECT name
            FROM main_categories
            ORDER BY name
        """
        return await DBService.fetch_data(query)
    
    @staticmethod
    async def get_subcategories_static(main_category_name: str):
        """
        Статический метод для получения списка подкатегорий.
        Не требует создания сессии.
        
        Args:
            main_category_name (str): Название основной категории
            
        Returns:
            list: Список словарей с подкатегориями
        """
        query = """
            SELECT id, name
            FROM categories
            WHERE main_category_name = :main_category_name
            ORDER BY name
        """
        return await DBService.fetch_data(query, {"main_category_name": main_category_name})
    
    @staticmethod
    async def get_supplier_by_id_static(supplier_id: int) -> dict:
        """
        Статический метод для получения информации о поставщике по ID.
        Не требует создания сессии.
        
        Args:
            supplier_id (int): ID поставщика
            
        Returns:
            dict: Информация о поставщике или None если поставщик не найден
        """
        try:
            # Получаем основную информацию о поставщике
            query = """
                SELECT 
                    s.id, s.company_name, s.product_name, s.category_id, 
                    s.description, s.country, s.region, s.city, s.address,
                    s.contact_username, s.contact_phone, s.contact_email,
                    s.created_at, s.status, s.created_by_id, s.tarrif,
                    c.name as category_name, mc.name as main_category_name
                FROM suppliers s
                LEFT JOIN categories c ON s.category_id = c.id
                LEFT JOIN main_categories mc ON c.main_category_name = mc.name
                WHERE s.id = :supplier_id
            """
            supplier_dict = await DBService.fetch_one(query, {"supplier_id": supplier_id})
            
            if not supplier_dict:
                return None
                
            # Получаем файлы поставщика
            files_query = """
                SELECT id, type, file_path, name, uploaded_at
                FROM files
                WHERE supplier_id = :supplier_id
                ORDER BY type, uploaded_at
            """
            files = await DBService.fetch_data(files_query, {"supplier_id": supplier_id})
            
            # Формируем структуру с фотографиями и видео
            photos = []
            video = None
            
            for file in files:
                if file["type"] == "photo":
                    photos.append(file)
                elif file["type"] == "video":
                    video = file
            
            supplier_dict["photos"] = photos
            supplier_dict["video"] = video
            
            return supplier_dict
            
        except Exception as e:
            logging.error(f"Error getting supplier by ID: {str(e)}")
            return None
    
    @staticmethod
    async def get_suppliers_by_subcategory_static(subcategory_id: int):
        """
        Статический метод для получения списка поставщиков по ID подкатегории.
        
        Args:
            subcategory_id (int): ID подкатегории
            
        Returns:
            list: Список поставщиков
        """
        query = """
            SELECT id FROM suppliers 
            WHERE category_id = :category_id AND status = 'pending'
            ORDER BY created_at DESC
        """
        return await DBService.fetch_data(query, {"category_id": subcategory_id})
    
    @staticmethod
    async def update_supplier_status(supplier_id: int, status: str):
        query = """
            UPDATE suppliers
            SET status = :status
            WHERE id = :supplier_id
        """
        await DBService.execute(query, {"supplier_id": supplier_id, "status": status})
    
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

    async def get_user_by_id(self, user_id: int):
        """Get user information by Telegram ID"""
        query = """
            SELECT tg_id, username, first_name, last_name, email, phone, role, created_at
            FROM users
            WHERE tg_id = :user_id
        """
        result = await self.execute_query(query, {"user_id": user_id})
        return result.mappings().first()
    
    async def get_main_categories(self):
        """Get list of main categories"""
        query = """
            SELECT name
            FROM main_categories
            ORDER BY name
        """
        result = await self.execute_query(query)
        return result.mappings().all()
    
    async def get_subcategories(self, main_category_name: str):
        """Get subcategories for a main category"""
        query = """
            SELECT id, name
            FROM categories
            WHERE main_category_name = :main_category_name
            ORDER BY name
        """
        result = await self.execute_query(query, {"main_category_name": main_category_name})
        return result.mappings().all()
    
    async def save_supplier(self, company_name: str, product_name: str, category_id: int,
                          description: str = None, country: str = None, region: str = None,
                          city: str = None, address: str = None, contact_username: str = None,
                          contact_phone: str = None, contact_email: str = None,
                          created_by_id: int = None, photos: list = None, video: dict = None) -> int:
        """Сохраняет информацию о поставщике в базу данных
        
        Args:
            company_name (str): Название компании
            product_name (str): Название продукта
            category_id (int): ID категории
            description (str, optional): Описание продукта
            country (str, optional): Страна
            region (str, optional): Регион
            city (str, optional): Город
            address (str, optional): Адрес
            contact_username (str, optional): Контактный username
            contact_phone (str, optional): Контактный телефон
            contact_email (str, optional): Контактный email
            created_by_id (int, optional): ID пользователя, создавшего поставщика
            photos (list, optional): Список фотографий, первое фото становится главным (is_top=True)
            video (dict, optional): Видео
            
        Returns:
            int: ID созданного поставщика
        """
        try:
            logging.info("=== Начало сохранения поставщика ===")
            logging.info(f"Данные: company_name={company_name}, product_name={product_name}, category_id={category_id}")
            logging.info(f"Фотографии: {len(photos) if photos else 0} шт.")
            logging.info(f"Видео: {video is not None}")
            
            # Сохраняем основную информацию о поставщике
            query = """
                INSERT INTO suppliers (
                    company_name, product_name, category_id, description,
                    country, region, city, address, contact_username,
                    contact_phone, contact_email, created_by_id
                )
                VALUES (
                    :company_name, :product_name, :category_id, :description,
                    :country, :region, :city, :address, :contact_username,
                    :contact_phone, :contact_email, :created_by_id
                )
                RETURNING id
            """
            params = {
                "company_name": company_name,
                "product_name": product_name,
                "category_id": category_id,
                "description": description,
                "country": country,
                "region": region,
                "city": city,
                "address": address,
                "contact_username": contact_username,
                "contact_phone": contact_phone,
                "contact_email": contact_email,
                "created_by_id": created_by_id
            }
            result = await self.execute_query(query, params)
            supplier_id = result.scalar_one()
            logging.info(f"Поставщик создан с ID: {supplier_id}")
            
            # Сохраняем фотографии, если они есть
            if photos is not None and len(photos) > 0:
                logging.info(f"Начинаю сохранение {len(photos)} фотографий")
                for i, photo in enumerate(photos, 1):
                    logging.info(f"Сохраняю фото {i}/{len(photos)}: {photo.get('file_id', 'неизвестно')}")
                    try:
                        file_id = await self.save_file(
                            file_path=photo["storage_path"],
                            file_type="photo",
                            name=f"photo_{i}.jpg",
                            supplier_id=supplier_id
                        )
                        logging.info(f"Фото {i} сохранено с ID: {file_id}")
                    except Exception as e:
                        logging.error(f"Ошибка при сохранении фото {i}: {str(e)}")
                        logging.error(f"Данные фото: {photo}")
                        raise
            
            # Сохраняем видео, если оно есть
            if video and isinstance(video, dict) and 'file_id' in video and 'storage_path' in video:
                logging.info(f"Начинаю сохранение видео: {video.get('file_id', 'неизвестно')}")
                try:
                    file_id = await self.save_file(
                        file_path=video["storage_path"],
                        file_type="video",
                        name=f"video_{video['file_id']}.mp4",
                        supplier_id=supplier_id
                    )
                    logging.info(f"Видео сохранено с ID: {file_id}")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении видео: {str(e)}")
                    logging.error(f"Данные видео: {video}")
                    raise
            
            # Выполняем коммит транзакции
            await self.commit()
            logging.info("=== Транзакция успешно завершена, поставщик сохранен ===")
            return supplier_id
            
        except Exception as e:
            # Выполняем откат транзакции при ошибке
            await self.rollback()
            logging.error(f"=== ОШИБКА при сохранении поставщика: {str(e)} ===")
            logging.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logging.error(f"Стек вызовов: {traceback.format_exc()}")
            raise

    async def save_file(self, file_path: str, file_type: str, name: str = None, 
                       request_id: int = None, supplier_id: int = None) -> int:
        """Сохраняет информацию о файле в базу данных"""
        try:
            logging.info(f"Сохранение файла: {file_type}, {name}, supplier_id={supplier_id}")
            # Проверяем корректность данных
            if not file_path:
                logging.error("file_path не может быть пустым")
                raise ValueError("file_path не может быть пустым")
                
            query = """
                INSERT INTO files (
                    type, file_path, name, request_id, supplier_id
                )
                VALUES (
                    :type, :file_path, :name, :request_id, :supplier_id
                )
                RETURNING id
            """
            params = {
                "type": file_type,
                "file_path": file_path,
                "name": name,
                "request_id": request_id,
                "supplier_id": supplier_id
            }
            logging.info(f"SQL параметры: {params}")
            result = await self.execute_query(query, params)
            file_id = result.scalar_one()
            logging.info(f"Файл сохранен с ID: {file_id}")
            return file_id
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении файла: {str(e)}")
            logging.error(f"Параметры: file_path={file_path}, file_type={file_type}, name={name}, supplier_id={supplier_id}")
            raise

    async def get_suppliers_by_ids(self, supplier_ids: list) -> list:
        """
        Получает информацию о нескольких поставщиках по списку ID.
        
        Args:
            supplier_ids (list): Список ID поставщиков
            
        Returns:
            list: Список словарей с информацией о поставщиках
        """
        if not supplier_ids:
            return []
            
        result = []
        for supplier_id in supplier_ids:
            supplier = await self.get_supplier_by_id(supplier_id)
            if supplier:
                result.append(supplier)
                
        return result

    async def fetch_all(self, query: str, params: dict = None) -> list:
        """Execute a query and return all results"""
        try:
            async with engine.begin() as conn:
                if params:
                    result = await conn.execute(text(query), params)
                else:
                    result = await conn.execute(text(query))
                return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Error executing query: {query[:100]}...")
            logger.error(f"Error details: {str(e)}")
            raise

    async def fetch_scalar(self, query: str, params: dict = None) -> Any:
        """Execute a query and return scalar value"""
        try:
            async with engine.begin() as conn:
                if params:
                    result = await conn.execute(text(query), params)
                else:
                    result = await conn.execute(text(query))
                return result.scalar()
        except Exception as e:
            logger.error(f"Error executing query: {query[:100]}...")
            logger.error(f"Error details: {str(e)}")
            raise
