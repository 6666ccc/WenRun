"""Opaque immutable storage for original files and serialized parse artifacts."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Protocol


_SAFE_NAME = re.compile(r"[^\w.()\- ]", re.UNICODE)


def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name.strip().strip(".")
    name = _SAFE_NAME.sub("_", name)[:180]
    return name or "document.bin"


class AssetStorage(Protocol):
    def put(self, data: bytes, *, suffix: str = "") -> tuple[str, str]: ...
    def get(self, storage_key: str) -> bytes: ...
    def delete(self, storage_key: str) -> None: ...


class LocalAssetStorage:
    """Store objects below a fixed, resolved root; callers only persist opaque keys."""

    def __init__(self, root: str):
        path = Path(root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        self.root = path.resolve(strict=True)

    def _target(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{2}/[a-f0-9]{32}(?:\.[a-z0-9]{1,12})?", key):
            raise ValueError("invalid asset key")
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("asset key escapes storage root")
        return target

    def put(self, data: bytes, *, suffix: str = "") -> tuple[str, str]:
        extension = suffix.lower().lstrip(".")
        if extension and not re.fullmatch(r"[a-z0-9]{1,12}", extension):
            extension = "bin"
        token = uuid.uuid4().hex
        key = f"{token[:2]}/{token}" + (f".{extension}" if extension else "")
        target = self._target(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + f".{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
        finally:
            if temp.exists():
                temp.unlink()
        return key, hashlib.sha256(data).hexdigest()

    def get(self, storage_key: str) -> bytes:
        return self._target(storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        target = self._target(storage_key)
        target.unlink(missing_ok=True)


class S3AssetStorage:
    """S3/MinIO backend selected by deployment configuration."""

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - deployment configuration path
            raise RuntimeError("S3 storage requires boto3") from exc
        bucket = os.getenv("RAG_S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("RAG_S3_BUCKET is required for RAG_STORAGE_BACKEND=s3")
        options = {"service_name": "s3", "region_name": os.getenv("RAG_S3_REGION", "us-east-1")}
        endpoint = os.getenv("RAG_S3_ENDPOINT_URL", "").strip()
        if endpoint:
            options["endpoint_url"] = endpoint
        self.bucket = bucket
        self.client = boto3.client(**options)

    def put(self, data: bytes, *, suffix: str = "") -> tuple[str, str]:
        token = uuid.uuid4().hex
        extension = suffix.lower().lstrip(".")
        key = f"rag/{token[:2]}/{token}" + (f".{extension}" if re.fullmatch(r"[a-z0-9]{1,12}", extension) else "")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption=os.getenv("RAG_S3_SSE", "AES256"))
        return key, hashlib.sha256(data).hexdigest()

    def get(self, storage_key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=storage_key)["Body"].read()

    def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)


def get_asset_storage() -> AssetStorage:
    backend = os.getenv("RAG_STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3AssetStorage()
    if backend != "local":
        raise RuntimeError("RAG_STORAGE_BACKEND must be local or s3")
    environment = os.getenv("RAG_ENVIRONMENT", "development").lower()
    default = "data/rag-assets"
    configured = os.getenv("RAG_STORAGE_DIR", default).strip()
    if environment == "production" and configured == default:
        raise RuntimeError("production local storage requires an explicit persistent RAG_STORAGE_DIR")
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return LocalAssetStorage(str(path))

