import os
import logging
from typing import Any, Dict, List, Optional, Tuple
import json
import asyncio

import httpx

from app.config import config
from app.services.database import DBService, get_db_session
from sqlalchemy import text
from app.utils.queue_worker import add_topic_to_queue

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
            from app.config import config
            if getattr(config, 'RECREATE_DB_SCHEMA', False):
                loop = asyncio.get_running_loop()
                loop.create_task(self.initialize_jokes_on_startup())
        except RuntimeError:
            # Комментарии и логи — только на английском, независимо от языка файла!
            logger.debug("Event loop is not running; initial jokes generation will need manual trigger")

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
        # Clean the response - remove leading/trailing whitespace
        cleaned = raw_json.strip()
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        
        if isinstance(data, dict) and "jokes" in data and isinstance(data["jokes"], list):
            items = data["jokes"]
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("Invalid jokes JSON format")
        
        jokes: List[Dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            joke_text = str(item.get("text", "")).strip()
            if topic and joke_text:
                jokes.append({"topic": topic, "text": joke_text})
        
        if len(jokes) == 0:
            raise ValueError("No valid jokes parsed from JSON")
        return jokes

    async def initialize_jokes_on_startup(self) -> Tuple[int, int]:
        logger.info("[DeepSeek] Initializing starter jokes (one-time)")
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
        
        # 2. Затем используем универсальную функцию retry для парсинга
        jokes = await self.parse_with_retry(
            content=content,
            parse_func=self._parse_jokes_json
        )

        # Persist to DB: create jokes with topics directly
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
                        await add_topic_to_queue(topic)
                        topic_id = await DBService.create_topic(topic, session=session)
                    except Exception:
                        query = "SELECT id FROM topics WHERE topic = :topic"
                        result = await session.execute(text(query), {"topic": topic})
                        row = result.mappings().first()
                        if row and "id" in row:
                            topic_id = int(row["id"])
                        else:
                            continue
                    topic_ids[topic] = topic_id
                else:
                    topic_id = topic_ids[topic]
                try:
                    await DBService.create_joke(topic_id, joke_text, session=session)
                    inserted_count += 1
                except Exception:
                    continue
            await session.commit()
        
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
        logger.debug(f"[DeepSeek] parse_with_retry called with content length: {len(content)}")
        
        try:
            return parse_func(content, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Parse error: {e}. Sending correction request to DeepSeek.")
            logger.error(f"[DeepSeek] PARSE FAIL: type={type(content)}, repr={repr(content)}, error={e}")
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

    async def request_jokes(self, topic: str, n: int = 5) -> str:
        """
        Запрашивает n анекдотов на заданную тему у DeepSeek, с учётом уже существующих анекдотов и реакций пользователей.
        """
        # Получаем topic_id
        jokes_context = ""
        topic_id = None
        # Получить topic_id
        from sqlalchemy import text
        async with get_db_session() as session:
            res = await session.execute(text("SELECT id FROM topics WHERE topic = :topic"), {"topic": topic})
            row = res.first()
            if row:
                topic_id = row.id
        if topic_id:
            jokes = await DBService.get_jokes_and_reactions_by_topic_id(topic_id)
            if jokes:
                jokes_context = "\n".join([
                    f"Анекдот: {j['joke']} | Лайков: {j['likes']} | Дизлайков: {j['dislikes']}"
                    for j in jokes
                ])
        # Формируем промт
        system_req = (
                "Ты — мастер анекдотов и сатиры.\n"
                "Твоя задача — придумать новые остроумные анекдоты для русскоязычной аудитории.\n\n"
                "Особенности:\n"
                "- Не повторяй и не перефразируй анекдоты из списка ниже.\n"
                "- Изучай реакции: анекдоты с лайками — смешные, бери их стиль как ориентир. Анекдоты с дизлайками — неудачные, избегай такого стиля.\n"
                "- Анекдоты должны быть свежими, с неожиданным поворотом, а не банальными или примитивными.\n"
                "- Допустим умный абсурд, самоирония, сатира, лёгкая острота и смелость — не бойся шутить так, как это принято в реальных русских анекдотах.\n"
                "- Избегай скучных коротких «шуток ради шутки». Пусть это будут именно анекдоты — с маленькой историей и punchline в конце.\n\n"
                "Пример хорошего анекдота (не для копирования, только как ориентир):\n"
                "— В семье канибалов умер дедушка...\n"
                "— Грустно, но вкусно.\n\n"
                f"Теперь создай {n} абсолютно новых анекдотов на тему «{topic}», которых нет в списке ниже.\n"
            

            "ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО В ВИДЕ ВАЛИДНОГО JSON-МАССИВА!\n"
            "- Не используй markdown-кодблоки, не добавляй никаких пояснений, комментариев, текста до или после массива.\n"
            "- Каждый элемент массива — объект с полем 'text'.\n"
            "- Пример правильного ответа: [{\"text\": \"Анекдот 1\"}, {\"text\": \"Анекдот 2\"}]\n"
            f"- Если не можешь придумать {n} анекдотов, верни столько, сколько получилось, но обязательно в виде массива.\n"
            "- Не добавляй никаких других полей, кроме 'text'.\n"
            "Ответ должен начинаться с '[' и заканчиваться ']'."
        )
        user_req = f"Тема: {topic}\n\nСписок существующих анекдотов и реакций:\n{jokes_context if jokes_context else 'Нет.'}\n\nСоздай {n} новых анекдотов."
        messages = self.build_messages([
            {"role": "system", "content": system_req},
            {"role": "user", "content": user_req},
        ])
        try:
            raw_response = await self._chat_completion(
                messages,
                model="deepseek-chat",
                temperature=0.8,
                max_tokens=1500,
            )
            content = raw_response["choices"][0]["message"]["content"]
            data = await self.parse_with_retry(
                content,
                self._parse_jokes_list
            )
            # Возвращаем обратно JSON-строку, чтобы не ломать интерфейс
            import json
            return json.dumps(data, ensure_ascii=False)
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
