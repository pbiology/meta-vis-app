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
#   close()                  — release any held resources (S3 only)

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
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

    async def close(self) -> None:
        """Release any held resources. No-op for backends that don't need it."""


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
        await self._db["blobs"].delete_many(
            {"key": {"$regex": f"^{re.escape(prefix)}"}}
        )


# ---------------------------------------------------------------------------
# S3-compatible object storage backend (MinIO / AWS S3)
#
# boto3 (urllib3-backed) consistently outperforms aiobotocore/aiohttp for large
# blob uploads to localhost MinIO. We wrap the synchronous client in a dedicated
# ThreadPoolExecutor so S3 threads are isolated from FastAPI's default executor,
# which is the actual fix for the thread-pool exhaustion concern.
# ---------------------------------------------------------------------------


class S3BlobStore(BlobStore):
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        max_workers: int = 10,
    ):
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="s3-blob"
        )
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                max_pool_connections=max_workers,
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=self._bucket)

    async def put(self, key: str, content: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
            ),
        )

    async def get(self, key: str) -> Optional[str]:
        from botocore.exceptions import ClientError

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                self._executor,
                lambda: self._s3.get_object(Bucket=self._bucket, Key=key),
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                return None
            raise

    async def delete_prefix(self, prefix: str) -> None:
        loop = asyncio.get_running_loop()

        def _delete() -> None:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    self._s3.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                    )

        await loop.run_in_executor(self._executor, _delete)

    async def close(self) -> None:
        self._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Factory — called once at startup, stored as singleton in database.py
# ---------------------------------------------------------------------------


def make_blob_store(db: AsyncIOMotorDatabase) -> BlobStore:
    from app.config import settings

    if settings.object_storage_endpoint:
        access_key = settings.object_storage_access_key or ""
        secret_key = settings.object_storage_secret_key or ""
        return S3BlobStore(
            endpoint=settings.object_storage_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=settings.object_storage_bucket,
        )
    return MongoBlobStore(db)
