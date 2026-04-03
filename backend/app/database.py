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
    await _ensure_indexes()


async def _ensure_indexes():
    db = client[settings.mongodb_db_name]

    # cases — fast lookup by case_id and filtering by order_date
    await db["cases"].create_index("case_id", unique=True)
    await db["cases"].create_index("ingested_at")
    await db["cases"].create_index("order_date")

    # samples — fast lookup by case, by case+type+material (NTC profiles),
    # and by viral taxa fields used in the outbreak aggregation pipeline
    await db["samples"].create_index("case_id")
    await db["samples"].create_index([("case_id", 1), ("sample_type", 1), ("material", 1)])
    await db["samples"].create_index("profiles.profile.superkingdom")
    await db["samples"].create_index("profiles.profile.taxon_id")

    # krona_files — fast lookup by case+classifier
    await db["krona_files"].create_index(
        [("case_id", 1), ("classifier", 1)], unique=True
    )

    # metaval_results — fast lookup by sample and case
    await db["metaval_results"].create_index("sample_id")
    await db["metaval_results"].create_index("case_id")

    # outbreak_ignorelist — fast lookup by taxon_id
    await db["outbreak_ignorelist"].create_index("taxon_id", unique=True)


async def close_db():
    global client
    if client:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    return client[settings.mongodb_db_name]
