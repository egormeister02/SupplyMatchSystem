import os
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
import asyncio

import httpx

from app.config import config
from app.services.database import DBService
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DeepSeekService:
    _instance: Optional["DeepSeekService"] = None

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_s: float = 60.0,
        primary_system_instructions: Optional[List[str]] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._client: Optional[httpx.AsyncClient] = None
        # Системные инструкции, которые будут добавляться первыми во все запросы
        self._system_messages: List[Dict[str, str]] = []
        if primary_system_instructions:
            for text in primary_system_instructions:
                if not text:
                    continue
                self._system_messages.append({"role": "system", "content": text})
        # Флаг одноразовой инициализации стартового набора анекдотов
        self._initial_jokes_generated: bool = False
        # Автозапуск генерации стартовых анекдотов
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.initialize_jokes_on_startup())
        except RuntimeError:
            # Комментарии и логи — только на английском, независимо от языка файла!
            logger.warning("Event loop is not running; initial jokes generation will need manual trigger")

    @classmethod
    def get_instance(
        cls,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: float = 60.0,
        primary_system_instructions: Optional[List[str]] = None,
    ) -> "DeepSeekService":
        """Singleton accessor. Creates an instance on first call."""
        if cls._instance is None:
            key = api_key or getattr(config, "DEEPSEEK_API_KEY", None) or os.getenv("DEEPSEEK_API_KEY")
            if not key:
                logger.warning("DeepSeek API key is not configured")
            url = (base_url or getattr(config, "DEEPSEEK_BASE_URL", None) or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")

            cls._instance = cls(
                api_key=key,
                base_url=url,
                timeout_s=timeout_s,
                primary_system_instructions=primary_system_instructions,
            )
        else:
            # Optional: extend system messages if provided later
            if primary_system_instructions:
                for text in primary_system_instructions:
                    if not text:
                        continue
                    cls._instance._system_messages.append({"role": "system", "content": text})
        return cls._instance

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                "Content-Type": "application/json",
            }
            self._client = httpx.AsyncClient(timeout=self._timeout_s, headers=headers)
        return self._client

    def build_messages(self, user_messages: List[Dict[str, Any]], history: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Compose final messages array with primary system instructions first.

        user_messages: e.g. [{"role": "user", "content": "..."}]
        history: optional prior exchanges, already in OpenAI format
        """
        messages: List[Dict[str, Any]] = []
        messages.extend(self._system_messages)
        if history:
            messages.extend(history)
        messages.extend(user_messages)
        return messages

    async def _chat_completion(self, messages: List[Dict[str, Any]], *, model: str = "deepseek-chat", response_format: Optional[Dict[str, Any]] = None, temperature: float = 0.2, max_tokens: int = 1500) -> Dict[str, Any]:
        """Low-level call to DeepSeek chat/completions."""
        client = await self._ensure_client()
        url = f"{self._base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        # Комментарии и логи — только на английском, независимо от языка файла!
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_jokes_json(raw_json: str) -> List[Dict[str, str]]:
        """Parses JSON string to list of jokes with required keys: topic, text."""
        print(f"DEBUG: Parsing JSON string of length {len(raw_json)}")
        
        # Clean the response - remove leading/trailing whitespace
        cleaned = raw_json.strip()
        
        print(f"DEBUG: Cleaned JSON: {repr(cleaned[:100])}...")
        
        try:
            data = json.loads(cleaned)
            print(f"DEBUG: Successfully parsed JSON")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to parse JSON: {e}")
            raise ValueError(f"Invalid JSON format: {e}")
        
        print(f"DEBUG: Parsed data type: {type(data)}")
        print(f"DEBUG: Parsed data: {repr(data)[:200]}...")
        
        if isinstance(data, dict) and "jokes" in data and isinstance(data["jokes"], list):
            items = data["jokes"]
            print(f"DEBUG: Found 'jokes' key with {len(items)} items")
        elif isinstance(data, list):
            items = data
            print(f"DEBUG: Data is a list with {len(items)} items")
        else:
            print(f"DEBUG: Invalid format - data is {type(data)}")
            raise ValueError("Invalid jokes JSON format")
        
        jokes: List[Dict[str, str]] = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                print(f"DEBUG: Item {i} is not a dict: {type(item)}")
                continue
            topic = str(item.get("topic", "")).strip()
            joke_text = str(item.get("text", "")).strip()
            print(f"DEBUG: Item {i}: topic='{topic}', text='{joke_text[:50]}...'")
            if topic and joke_text:
                jokes.append({"topic": topic, "text": joke_text})
        
        print(f"DEBUG: Successfully parsed {len(jokes)} jokes")
        if len(jokes) == 0:
            raise ValueError("No valid jokes parsed from JSON")
        return jokes

    async def initialize_jokes_on_startup(self) -> Tuple[int, int]:
        logger.info("[DeepSeek] Called initialize_jokes_on_startup")
        if self._initial_jokes_generated:
            return (-1, 0)

        system_req = (
            "Ты должен вернуть ТОЛЬКО валидный JSON-массив без каких-либо дополнительных символов, "
            "пробелов или текста. Каждый элемент массива должен быть объектом с полями 'topic' и 'text'. "
            "Ответ должен начинаться с '[' и заканчиваться ']'. Никаких комментариев или пояснений."
        )
        user_req = (
            "Сгенерируй 10 анекдотов средней длинны на 5 разных тем (по 2 анекдота на тему) на русском языке. "
            "Верни ТОЛЬКО JSON-массив в следующем формате:\n"
            "[\n"
            '  {"topic": "тема1", "text": "анекдот1"},\n'
            '  {"topic": "тема2", "text": "анекдот2"},\n'
            '  ...\n'
            "]\n"
            "Каждый объект должен содержать ровно два поля: 'topic' (строка с темой) и 'text' (строка с анекдотом). "
            "Никаких других полей или дополнительного текста."
        )
        messages = self.build_messages([
            {"role": "system", "content": system_req},
            {"role": "user", "content": user_req},
        ])

        # 1. Сначала получаем ответ от DeepSeek
        data = await self._chat_completion(
            messages,
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=2000,
        )
        content = data["choices"][0]["message"]["content"]
        
        # Debug: print the raw response from DeepSeek
        print(f"DEBUG: Raw response from DeepSeek:")
        print(f"DEBUG: {repr(content)}")
        print(f"DEBUG: Content length: {len(content)}")
        print(f"DEBUG: First 200 chars: {content[:200]}")
        print(f"DEBUG: Last 200 chars: {content[-200:]}")
        
        # 2. Затем используем универсальную функцию retry для парсинга
        jokes = await self.parse_with_retry(
            content=content,
            parse_func=self._parse_jokes_json
        )

        # Persist to DB: create jokes with topics directly
        print(f"DEBUG: Starting database operations...")
        print(f"DEBUG: Creating jokes with topics...")
        from app.services.database import get_db_session
        topic_ids = {}
        inserted_count = 0
        async with get_db_session() as session:
            for joke in jokes:
                topic = joke["topic"].strip()
                joke_text = joke["text"].strip()
                if not topic or not joke_text:
                    continue
                if topic not in topic_ids:
                    try:
                        topic_id = await DBService.create_topic(topic, session=session)
                    except Exception as e:
                        print(f"DEBUG: Exception on create_topic: {e}, trying to fetch existing topic id")
                        query = "SELECT id FROM topics WHERE topic = :topic"
                        result = await session.execute(text(query), {"topic": topic})
                        row = result.mappings().first()
                        if row and "id" in row:
                            topic_id = int(row["id"])
                        else:
                            print(f"DEBUG: Failed to get topic_id for topic: {topic}")
                            continue
                    topic_ids[topic] = topic_id
                else:
                    topic_id = topic_ids[topic]
                try:
                    await DBService.create_joke(topic_id, joke_text, session=session)
                    inserted_count += 1
                except Exception as e:
                    print(f"DEBUG: Failed to insert joke for topic_id={topic_id}: {e}")
                    continue
            await session.commit()
        print(f"DEBUG: Created {inserted_count} jokes")
        
        if inserted_count > 0:
            self._initial_jokes_generated = True
            logger.info(f"Successfully initialized {inserted_count} jokes with topics")
            return (1, inserted_count)  # Возвращаем topic_id = 1 и количество
        else:
            logger.error("Failed to create jokes with topics")
            return (-1, 0)

    async def close(self) -> None:
        client = self._client
        if self._client is not None:
            try:
                await client.aclose()
            except Exception as e:
                logger.error(f"Error closing DeepSeek HTTP client: {e}")
            finally:
                self._client = None

    async def parse_with_retry(
        self,
        content: str,
        parse_func,
        *args,
        **kwargs
    ):
        """
        Универсальная функция для парсинга с retry логикой.
        Принимает готовый контент от DeepSeek и функцию парсинга.
        При ошибке парсинга отправляет повторный запрос с просьбой исправить формат.
        """
        logger.info(f"[DeepSeek] parse_with_retry called with content length: {len(content)}")
        
        try:
            return parse_func(content, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Parse error: {e}. Sending correction request to DeepSeek.")
            fix_prompt = (
                "Исправь формат ответа и верни ТОЛЬКО валидный JSON без каких-либо комментариев, пояснений, преамбулы, "
                "без markdown-кодблоков (никаких ``` или ```json), без завершающего текста. Должен быть только JSON.\n"
                "Требования:\n"
                "- Строгий JSON, корректно экранированные кавычки.\n"
                "- Никаких лишних полей; используйте только требуемые (например, topic и text, если они ожидались).\n"
                "- Никаких висячих запятых, никакого лишнего текста до или после JSON.\n"
                "- Ответ должен начинаться с '[' и заканчиваться ']', если ожидался массив.\n"
                "- Если ранее прислал markdown-кодблок, УДАЛИ ограждения.\n\n"
                "Перешли этот же контент В СТРОГОМ JSON без обёрток и ошибок:\n"
                f"{content}"
            )
            fix_messages = self.build_messages([{"role": "user", "content": fix_prompt}])
            fix_data = await self._chat_completion(fix_messages)
            fix_content = fix_data["choices"][0]["message"]["content"]
            return parse_func(fix_content, *args, **kwargs)

    async def request_joke(self, topic: str) -> str:
        """Запрашивает анекдот на заданную тему у DeepSeek"""
        system_req = (
            "Ты - мастер анекдотов. Создай один смешной анекдот на заданную тему. "
            "Анекдот должен быть коротким, понятным и действительно смешным. "
            "Отвечай ТОЛЬКО текстом анекдота, без дополнительных комментариев."
        )
        
        user_req = f"Создай смешной анекдот на тему: {topic}"
        
        messages = self.build_messages([
            {"role": "system", "content": system_req},
            {"role": "user", "content": user_req},
        ])
        
        try:
            data = await self._chat_completion(
                messages,
                model="deepseek-chat",
                temperature=0.8,
                max_tokens=500,
            )
            
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error requesting joke from DeepSeek: {str(e)}")
            raise

    async def request_jokes(self, topic: str, n: int = 5) -> str:
        """
        Запрашивает n анекдотов на заданную тему у DeepSeek
        """
        system_req = (
            "Ты - мастер анекдотов. Создай несколько смешных анекдотов на заданную тему. "
            f"Верни ТОЛЬКО JSON-массив из {n} объектов, каждый с полями 'text'. Никаких других полей, комментариев или пояснений. "
            "Ответ должен начинаться с '[' и заканчиваться ']'."
        )
        user_req = f"Создай {n} смешных анекдотов на тему: {topic}"
        messages = self.build_messages([
            {"role": "system", "content": system_req},
            {"role": "user", "content": user_req},
        ])
        try:
            data = await self._chat_completion(
                messages,
                model="deepseek-chat",
                temperature=0.8,
                max_tokens=1500,
            )
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error requesting jokes from DeepSeek: {str(e)}")
            raise

    @staticmethod
    def _parse_jokes_list(content: str) -> list:
        """
        Парсит ответ с массивом анекдотов (каждый объект с ключом 'text')
        """
        import json
        cleaned = content.strip()
        try:
            data = json.loads(cleaned)
        except Exception as e:
            raise ValueError(f"Invalid JSON: {e}")
        if not isinstance(data, list):
            raise ValueError("Expected a list of jokes")
        jokes = []
        for item in data:
            if isinstance(item, dict) and "text" in item and item["text"].strip():
                jokes.append({"text": item["text"].strip()})
        if not jokes:
            raise ValueError("No valid jokes found")
        return jokes

    async def save_jokes_to_db(self, topic: str, jokes: list, user_id: int, selected_idx: int) -> tuple:
        """
        Сохраняет все анекдоты в jokes, а в users_jokes — только выбранный пользователю анекдот.
        Возвращает (topic_id, [joke_id, ...], users_jokes_id)
        """
        from app.services.database import get_db_session, DBService
        from sqlalchemy import text
        joke_ids = []
        users_jokes_id = None
        async with get_db_session() as session:
            topic_id = await DBService.create_topic(topic, session=session)
            for idx, joke in enumerate(jokes):
                joke_id = await DBService.create_joke(topic_id, joke["text"], session=session)
                joke_ids.append(joke_id)
                if idx == selected_idx:
                    res = await session.execute(
                        text(
                            """
                            INSERT INTO users_jokes (user_id, joke_id, reaction)
                            VALUES (:user_id, :joke_id, 'skip')
                            ON CONFLICT (user_id, joke_id) DO UPDATE SET reaction = 'skip'
                            RETURNING id
                            """
                        ),
                        {"user_id": user_id, "joke_id": joke_id}
                    )
                    users_jokes_id_row = res.first()
                    users_jokes_id = users_jokes_id_row[0] if users_jokes_id_row else None
            await session.commit()
        return topic_id, joke_ids, users_jokes_id

    @staticmethod
    def _parse_single_joke(content: str) -> dict:
        """Парсит ответ с одним анекдотом"""
        # Очищаем контент от лишних символов
        cleaned = content.strip()
        
        # Убираем возможные префиксы
        prefixes_to_remove = [
            "Анекдот:",
            "Вот анекдот:",
            "Анекдот на эту тему:",
            "Смешной анекдот:",
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        if not cleaned:
            raise ValueError("Empty joke content")
        
        return {"text": cleaned}


__all__ = ["DeepSeekService"]
