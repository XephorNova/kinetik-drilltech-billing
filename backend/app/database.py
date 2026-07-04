from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

_client = AsyncIOMotorClient(settings.MONGO_URL)
_db = _client[settings.MONGO_DB_NAME]


def get_db():
    return _db
