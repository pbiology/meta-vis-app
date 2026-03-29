#!/usr/bin/env python
"""
Create a user in the meta-vis-dev database.

Usage:
    python create_user.py --username admin --password secret

Run from the backend/ directory with the conda env active.
"""
import argparse
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "meta-vis-dev"


async def create_user(username: str, password: str):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db["users"].find_one({"username": username})
    if existing:
        print(f"User '{username}' already exists.")
        return

    await db["users"].insert_one({
        "username": username,
        "password_hash": pwd_context.hash(password),
    })
    print(f"User '{username}' created.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(create_user(args.username, args.password))