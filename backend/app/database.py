from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)


async def close_db():
    global client
    if client:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    return client[settings.mongodb_db_name]