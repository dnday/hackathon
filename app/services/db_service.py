from __future__ import annotations
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


def _save_scraped_listings_sync(listings: list[dict[str, Any]]) -> None:
    client = get_firestore_client()
    if client is None or not listings:
        return

    batch = client.batch()
    collection = client.collection("scraped_listings")
    
    for item in listings:
        url = item.get("listing_url", "")
        if not url:
            continue
            
        doc_id = url.split("/")[-1] or _document_id(item.get("listing_name", "unknown"))
        doc_ref = collection.document(doc_id)
        
        batch.set(doc_ref, {
            **item,
            "updated_at": datetime.now(UTC),
            "is_scraped": True
        }, merge=True)
    
    try:
        batch.commit(timeout=5)
    except Exception:
        pass


async def save_scraped_listings(listings: list[dict[str, Any]]) -> None:
    await asyncio.to_thread(_save_scraped_listings_sync, listings)


def _is_firestore_available_sync() -> bool:
    return get_firestore_client() is not None


async def is_firestore_available() -> bool:
    return await asyncio.to_thread(_is_firestore_available_sync)


def _fetch_scraped_listing_sync(url: str) -> dict[str, Any] | None:
    client = get_firestore_client()
    if client is None:
        return None

    try:
        docs = client.collection("scraped_listings").where("listing_url", "==", url).limit(1).get(retry=None, timeout=3)
        if not docs:
            return None
        data = docs[0].to_dict() or {}
        data["id"] = docs[0].id
        return data
    except google_exceptions.GoogleAPICallError:
        return None


async def fetch_scraped_listing(url: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_fetch_scraped_listing_sync, url)


__all__ = [
    "fetch_latest_area_benchmark",
    "initialize_firebase",
    "is_firestore_available",
    "save_market_benchmark",
    "save_validation_history",
    "save_scraped_listings",
    "fetch_scraped_listing",
]
