from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

client: AsyncIOMotorClient = None


def _build_mongo_url() -> str:
    if settings.mongodb_username and settings.mongo_app_password:
        return (
            f"mongodb://{settings.mongodb_username}:{settings.mongo_app_password}"
            f"@{settings.mongodb_host}:{settings.mongodb_port}"
            f"/{settings.mongodb_db_name}?authSource={settings.mongodb_auth_source}"
        )
    return f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}"


async def connect_db():
    global client
    client = AsyncIOMotorClient(_build_mongo_url())


async def close_db():
    global client
    if client:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    return client[settings.mongodb_db_name]
