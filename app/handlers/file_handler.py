"""
File upload and download handlers
"""

import logging
import os
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, Document, FSInputFile
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import local_storage_service, get_db_session, DBService

# Router initialization
router = Router()

@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Document upload handler"""
    document = message.document
    
    # Get file information
    file_name = document.file_name
    mime_type = document.mime_type
    
    try:
        # Download file to temporary directory
        file_info = await bot.get_file(document.file_id)
        file_path = file_info.file_path
        download_path = f"temp_{document.file_id}"
        await bot.download_file(file_path, download_path)
        
        # Save file to local storage
        file_relative_path = await local_storage_service.save_file(download_path, file_name)
        
        # Save file information to database
        async with get_db_session() as session:
            db_service = DBService(session)
            await save_file_to_db(db_service, file_relative_path, file_name, message)
        
        # Remove temporary file
        if os.path.exists(download_path):
            os.remove(download_path)
        
        await message.answer(f"Файл '{file_name}' успешно загружен!")
        
    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        await message.answer("Произошла ошибка при обработке файла. Попробуйте позже.")

@router.message(Command("getfile"))
async def get_file_command(message: Message, bot: Bot):
    """Command to get file by ID"""
    # Example format: /getfile 123
    command_parts = message.text.split()
    
    if len(command_parts) != 2:
        await message.answer("Использование: /getfile <id файла>")
        return
    
    try:
        file_id = int(command_parts[1])
        
        # Get file information from database
        async with get_db_session() as session:
            db_service = DBService(session)
            file_info = await get_file_from_db(db_service, file_id)
            
        if not file_info:
            await message.answer("Файл не найден.")
            return
            
        # Get full path to file
        file_path = await local_storage_service.get_file_path(file_info["file_path"])
        
        if not file_path:
            await message.answer("Файл не найден в хранилище.")
            return
            
        # Send file to user
        file_to_send = FSInputFile(file_path, filename=file_info["name"])
        await message.answer_document(file_to_send, caption=f"Файл: {file_info['name']}")
        
    except ValueError:
        await message.answer("ID файла должен быть числом.")
    except Exception as e:
        logging.error(f"Error retrieving file: {str(e)}")
        await message.answer("Произошла ошибка при получении файла.")

async def save_file_to_db(db_service: DBService, file_path: str, file_name: str, message: Message) -> Optional[int]:
    """Save file information to database"""
    try:
        # Determine file type by extension
        file_ext = os.path.splitext(file_name)[1].lower()
        file_type = "document"
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            file_type = "image"
        elif file_ext in ['.mp4', '.avi', '.mov']:
            file_type = "video"
            
        # Insert record into database
        query = """
            INSERT INTO files (type, file_path, name, uploaded_at)
            VALUES (:type, :file_path, :name, NOW())
            RETURNING id
        """
        result = await db_service.execute_query(
            query,
            {
                "type": file_type, 
                "file_path": file_path,
                "name": file_name
            }
        )
        file_id = result.scalar_one()
        await db_service.commit()
        
        return file_id
    except Exception as e:
        await db_service.rollback()
        await local_storage_service.delete_file(file_path)
        logging.error(f"Error saving file to database: {str(e)}")
        return None

async def get_file_from_db(db_service: DBService, file_id: int) -> Optional[dict]:
    """
    Get file information from database
    
    Args:
        db_service: DBService instance
        file_id: File ID
        
    Returns:
        Dictionary with file information or None if file not found
    """
    try:
        query = """
            SELECT id, type, file_path, name, uploaded_at
            FROM files
            WHERE id = :file_id
        """
        result = await db_service.execute_query(query, {"file_id": file_id})
        file_row = result.fetchone()
        
        if not file_row:
            return None
            
        return {
            "id": file_row[0],
            "type": file_row[1],
            "file_path": file_row[2],
            "name": file_row[3],
            "uploaded_at": file_row[4]
        }
    except Exception as e:
        logging.error(f"Error retrieving file from database: {str(e)}")
        return None 