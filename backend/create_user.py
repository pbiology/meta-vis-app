#!/usr/bin/env python
"""
Create a user in the meta-vis-dev database.

Usage:
    python create_user.py --username admin --password secret --role admin
"""
import argparse
import asyncio
import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _build_mongo_url() -> str:
    # Use root credentials to bootstrap user creation
    username = os.getenv("MONGO_INITDB_ROOT_USERNAME", "admin")
    password = os.getenv("MONGO_ROOT_PASSWORD")
    host     = os.getenv("MONGODB_HOST", "localhost")
    port     = os.getenv("MONGODB_PORT", "27017")
    if password:
        return f"mongodb://{username}:{password}@{host}:{port}/?authSource=admin"
    return f"mongodb://{host}:{port}"


async def create_user(username: str, password: str, role: str):
    db_name = os.getenv("MONGODB_DB_NAME", "meta-vis-dev")
    client  = AsyncIOMotorClient(_build_mongo_url())
    db      = client[db_name]

    existing = await db["users"].find_one({"username": username})
    if existing:
        print(f"User '{username}' already exists.")
        client.close()
        return

    await db["users"].insert_one({
        "username":      username,
        "password_hash": pwd_context.hash(password),
        "role":          role,
    })
    print(f"User '{username}' created with role '{role}'.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="reader", choices=["reader", "writer", "admin"])
    args = parser.parse_args()
    asyncio.run(create_user(args.username, args.password, args.role))