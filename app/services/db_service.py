from __future__ import annotations
import asyncio
from datetime import timezone, datetime
from typing import Any, Optional

from google.api_core import exceptions as google_exceptions

from app.core.config import get_settings
from app.core.firebase_init import get_firestore_client, initialize_firebase


def _document_id(area_name: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in area_name
    )
    return "-".join(part for part in normalized.split("-") if part) or "unknown-area"


def _fetch_latest_area_benchmark_sync(area_name: str) -> Optional[dict[str, Any]]:
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


async def fetch_latest_area_benchmark(area_name: str) -> Optional[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_latest_area_benchmark_sync, area_name)


def _save_market_benchmark_sync(area_name: str, payload: dict[str, Any]) -> Optional[str]:
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
                "updated_at": datetime.now(timezone.utc),
            },
            retry=None,
            timeout=3,
        )
    except google_exceptions.GoogleAPICallError:
        return None
    return document_id


async def save_market_benchmark(area_name: str, payload: dict[str, Any]) -> Optional[str]:
    return await asyncio.to_thread(_save_market_benchmark_sync, area_name, payload)


def _save_validation_history_sync(payload: dict[str, Any]) -> Optional[str]:
    client = get_firestore_client()
    if client is None:
        return None

    settings = get_settings()
    document = client.collection(settings.firestore_history_collection).document()
    try:
        document.set(
            {**payload, "created_at": datetime.now(timezone.utc)},
            retry=None,
            timeout=3,
        )
    except google_exceptions.GoogleAPICallError:
        return None
    return document.id


async def save_validation_history(payload: dict[str, Any]) -> Optional[str]:
    return await asyncio.to_thread(_save_validation_history_sync, payload)


def _fetch_validation_history_sync(device_id: str, limit: int = 20) -> list[dict[str, Any]]:
    client = get_firestore_client()
    if client is None:
        return []
    settings = get_settings()
    try:
        docs = (
            client.collection(settings.firestore_history_collection)
            .where("form_data.device_id", "==", device_id)
            .get(retry=None, timeout=5)
        )
        results = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        
        # Sort in memory to avoid composite index requirement
        results.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return results[:limit]
    except google_exceptions.GoogleAPICallError:
        return []


async def fetch_validation_history(device_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_validation_history_sync, device_id, limit)


def _fetch_validation_record_sync(record_id: str) -> Optional[dict[str, Any]]:
    client = get_firestore_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        doc = client.collection(settings.firestore_history_collection).document(record_id).get(retry=None, timeout=3)
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return data
    except google_exceptions.GoogleAPICallError:
        return None


async def fetch_validation_record_by_id(record_id: str) -> Optional[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_validation_record_sync, record_id)


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
            "updated_at": datetime.now(timezone.utc),
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


def _fetch_scraped_listing_sync(url: str) -> Optional[dict[str, Any]]:
    client = get_firestore_client()
    if client is None:
        return None

    try:
        docs = client.collection("scraped_listings").where("listing_url", "==", url).limit(1).get(retry=None, timeout=3)
        if not docs:
            return None
        data = docs[0].to_dict() or {}
        # Force re-scrape if it's old cached data without the new enriched fields (like 'source')
        if "source" not in data:
            return None
        return data
    except google_exceptions.GoogleAPICallError:
        return None


async def fetch_scraped_listing(url: str) -> Optional[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_scraped_listing_sync, url)


def _append_kos_review_sync(kos_id: str, review_data: dict[str, Any]) -> None:
    client = get_firestore_client()
    if not client: return
    
    from google.cloud import firestore
    try:
        doc_ref = client.collection("scraped_listings").document(kos_id)
        doc_ref.set({"user_reviews": firestore.ArrayUnion([review_data])}, merge=True)
    except Exception as e:
        print(f"Failed to append review: {e}")

async def append_kos_review(kos_id: str, review_data: dict[str, Any]) -> None:
    await asyncio.to_thread(_append_kos_review_sync, kos_id, review_data)

__all__ = [
    "fetch_latest_area_benchmark",
    "initialize_firebase",
    "is_firestore_available",
    "save_market_benchmark",
    "save_validation_history",
    "fetch_validation_history",
    "fetch_validation_record_by_id",
    "save_scraped_listings",
    "fetch_scraped_listing",
    "append_kos_review",
]
