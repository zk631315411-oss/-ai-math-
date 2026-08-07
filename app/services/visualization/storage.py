"""Private S3-compatible artifact storage."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Iterable

from app.config import config


def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=config.VISUALIZATION_S3_ENDPOINT or None,
        region_name=config.VISUALIZATION_S3_REGION,
        aws_access_key_id=config.VISUALIZATION_S3_ACCESS_KEY,
        aws_secret_access_key=config.VISUALIZATION_S3_SECRET_KEY,
        config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2}),
    )


def ensure_bucket() -> None:
    client = _client()
    try:
        client.head_bucket(Bucket=config.VISUALIZATION_S3_BUCKET)
    except Exception:
        kwargs = {"Bucket": config.VISUALIZATION_S3_BUCKET}
        if config.VISUALIZATION_S3_REGION != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": config.VISUALIZATION_S3_REGION}
        client.create_bucket(**kwargs)


def upload_file(path: str | Path, key: str, content_type: str) -> None:
    ensure_bucket()
    _client().upload_file(
        str(path),
        config.VISUALIZATION_S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def presign_get(key: str | None) -> str | None:
    if not key:
        return None
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.VISUALIZATION_S3_BUCKET, "Key": key},
        ExpiresIn=config.VISUALIZATION_URL_TTL_SECONDS,
    )


def delete_objects(keys: Iterable[str]) -> None:
    normalized = list(dict.fromkeys(key for key in keys if key))
    if not normalized:
        return
    try:
        _client().delete_objects(
            Bucket=config.VISUALIZATION_S3_BUCKET,
            Delete={"Objects": [{"Key": key} for key in normalized], "Quiet": True},
        )
    except Exception:
        # Chat deletion must not fail solely because object storage is offline.
        return


def schedule_delete_objects(keys: Iterable[str]) -> None:
    normalized = list(dict.fromkeys(key for key in keys if key))
    if normalized:
        threading.Thread(target=delete_objects, args=(normalized,), daemon=True).start()
