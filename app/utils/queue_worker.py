import asyncio
from typing import Set
# from app.services.deepseek import DeepSeekService
from app.services.database import get_db_session
from sqlalchemy import text
import logging
from app.config import config

logger = logging.getLogger(__name__)

try:
    from aiolimiter import AsyncLimiter
except ImportError:
    AsyncLimiter = None  # Если не установлен, будет ошибка при запуске

# In-memory очередь тем
class TopicQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self._topics_in_queue: Set[str] = set()  # Для защиты от дублей

    async def add_topic(self, topic: str):
        if topic not in self._topics_in_queue:
            await self.queue.put(topic)
            self._topics_in_queue.add(topic)
            logger.info(f"Topic added to queue: {topic}")
        else:
            logger.debug(f"Topic already in queue: {topic}")

    async def get_topic(self) -> str:
        topic = await self.queue.get()
        self._topics_in_queue.discard(topic)
        return topic

    def size(self) -> int:
        return self.queue.qsize()

topic_queue = TopicQueue()

# Rate limiter: 55 запросов в минуту (DeepSeek лимит)
RATE_LIMIT = 55  # запросов в минуту
if AsyncLimiter:
    limiter = AsyncLimiter(RATE_LIMIT, time_period=60)
else:
    limiter = None

# Один воркер очереди
async def topic_queue_worker():
    # Локальный импорт для избежания циклической зависимости
    from app.services.deepseek import DeepSeekService
    deepseek = DeepSeekService.get_instance()
    while True:
        topic = await topic_queue.get_topic()
        logger.info(f"Processing topic from queue: {topic}")
        try:
            if limiter:
                async with limiter:
                    import json
                    jokes = json.loads(await deepseek.request_jokes(topic, n=5))
            else:
                import json
                jokes = json.loads(await deepseek.request_jokes(topic, n=5))
            await deepseek.save_jokes_to_db(topic, jokes, user_id=0, selected_idx=None)
            logger.info(f"Saved 5 jokes for topic: {topic}")
        except Exception as e:
            logger.error(f"Error processing topic '{topic}': {e}")
        # Без sleep — лимитер сам ограничивает скорость

# Запуск всех воркеров
async def start_topic_queue_workers():
    workers = []
    for _ in range(config.QUEUE_WORKERS):
        workers.append(asyncio.create_task(topic_queue_worker()))
    logger.info(f"Запущено {config.QUEUE_WORKERS} воркеров очереди тем.")
    await asyncio.gather(*workers)

# Функция для ручного добавления темы в очередь
async def add_topic_to_queue(topic: str):
    await topic_queue.add_topic(topic)

# Функция для проверки пользователей и добавления тем в очередь
async def refill_queue_for_users_with_few_jokes():
    """
    Для всех пользователей, у которых <=4 непрочитанных анекдота,
    берём их последнюю тему (last_topics.topic) и добавляем в очередь.
    """
    async with get_db_session() as session:
        # Получаем пользователей с <=4 непрочитанных анекдотов
        query = text('''
            SELECT uuj.tg_id, COUNT(uuj.joke_id) as unheard_count, lt.topic
            FROM user_unheard_jokes uuj
            JOIN last_topics lt ON lt.tg_id = uuj.tg_id
            GROUP BY uuj.tg_id, lt.topic
            HAVING COUNT(uuj.joke_id) <= 7
        ''')
        result = await session.execute(query)
        rows = result.fetchall()
        for row in rows:
            topic = row.topic
            await topic_queue.add_topic(topic)
            logger.info(f"Added topic '{topic}' for user {row.tg_id} to queue (unheard jokes: {row.unheard_count})") 