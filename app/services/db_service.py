import asyncio
from datetime import UTC, datetime
from typing import Any

from google.api_core import exceptions as google_exceptions

from app.core.config import get_settings
from app.core.firebase_init import get_firestore_client, initialize_firebase


def _document_id(area_name: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in area_name
    )
    return "-".join(part for part in normalized.split("-") if part) or "unknown-area"


def _fetch_latest_area_benchmark_sync(area_name: str) -> dict[str, Any] | None:
    client = get_firestore_client()
    if client is None:
        return None

    settings = get_settings()
    try:
        document = (
            client.collection(settings.firestore_benchmark_collection)
            .document(_document_id(area_name))
            .get(retry=None, timeout=3)
        )
    except (
        google_exceptions.Forbidden,
        google_exceptions.PermissionDenied,
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        google_exceptions.GoogleAPICallError,
    ):
        return None
    if not document.exists:
        return None
    data = document.to_dict() or {}
    data["id"] = document.id
    return data


async def fetch_latest_area_benchmark(area_name: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_fetch_latest_area_benchmark_sync, area_name)


def _save_market_benchmark_sync(area_name: str, payload: dict[str, Any]) -> str | None:
    client = get_firestore_client()
    if client is None:
        return None

    settings = get_settings()
    document_id = _document_id(area_name)
    try:
        client.collection(settings.firestore_benchmark_collection).document(document_id).set(
            {
                **payload,
                "area_name": area_name,
                "updated_at": datetime.now(UTC),
            },
            retry=None,
            timeout=3,
        )
    except google_exceptions.GoogleAPICallError:
        return None
    return document_id


async def save_market_benchmark(area_name: str, payload: dict[str, Any]) -> str | None:
    return await asyncio.to_thread(_save_market_benchmark_sync, area_name, payload)


def _save_validation_history_sync(payload: dict[str, Any]) -> str | None:
    client = get_firestore_client()
    if client is None:
        return None

    settings = get_settings()
    document = client.collection(settings.firestore_history_collection).document()
    try:
        document.set(
            {**payload, "created_at": datetime.now(UTC)},
            retry=None,
            timeout=3,
        )
    except google_exceptions.GoogleAPICallError:
        return None
    return document.id


async def save_validation_history(payload: dict[str, Any]) -> str | None:
    return await asyncio.to_thread(_save_validation_history_sync, payload)


def _is_firestore_available_sync() -> bool:
    return get_firestore_client() is not None


async def is_firestore_available() -> bool:
    return await asyncio.to_thread(_is_firestore_available_sync)


__all__ = [
    "fetch_latest_area_benchmark",
    "initialize_firebase",
    "is_firestore_available",
    "save_market_benchmark",
    "save_validation_history",
]
