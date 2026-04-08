# app/blob_store.py
#
# Storage abstraction for large HTML blobs (Krona files).
# Two backends: MongoDB (default) and S3-compatible object storage (MinIO / AWS S3).
# Config decides which backend is used at startup via make_blob_store().
#
# Key conventions:
#   krona/{case_object_id}/{classifier}.html
#
# Both backends expose the same interface:
#   put(key, content)        — store content at key
#   get(key)                 — retrieve content, returns None if not found
#   delete_prefix(prefix)    — delete all objects whose key starts with prefix

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class BlobStore(ABC):
    @abstractmethod
    async def put(self, key: str, content: str) -> None:
        """Store content at key."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve content at key. Returns None if not found."""

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Delete all objects whose key starts with prefix."""


# ---------------------------------------------------------------------------
# MongoDB backend (default)
# ---------------------------------------------------------------------------


class MongoBlobStore(BlobStore):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def put(self, key: str, content: str) -> None:
        from datetime import datetime, timezone

        await self._db["blobs"].replace_one(
            {"key": key},
            {"key": key, "content": content, "stored_at": datetime.now(timezone.utc)},
            upsert=True,
        )

    async def get(self, key: str) -> Optional[str]:
        doc = await self._db["blobs"].find_one({"key": key}, {"content": 1})
        return doc["content"] if doc else None

    async def delete_prefix(self, prefix: str) -> None:
        await self._db["blobs"].delete_many({"key": {"$regex": f"^{prefix}"}})


# ---------------------------------------------------------------------------
# S3-compatible object storage backend (MinIO / AWS S3)
# ---------------------------------------------------------------------------


class S3BlobStore(BlobStore):
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except Exception:
            self._s3.create_bucket(Bucket=self._bucket)

    async def put(self, key: str, content: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
            ),
        )

    async def get(self, key: str) -> Optional[str]:
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._s3.get_object(Bucket=self._bucket, Key=key),
            )
            return response["Body"].read().decode("utf-8")
        except Exception:
            return None

    async def delete_prefix(self, prefix: str) -> None:
        loop = asyncio.get_running_loop()

        def _delete():
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    self._s3.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                    )

        await loop.run_in_executor(None, _delete)


# ---------------------------------------------------------------------------
# Factory — called once at startup, stored as singleton in database.py
# ---------------------------------------------------------------------------


def make_blob_store(db: AsyncIOMotorDatabase) -> BlobStore:
    from app.config import settings

    if settings.object_storage_endpoint:
        return S3BlobStore(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
        )
    return MongoBlobStore(db)
