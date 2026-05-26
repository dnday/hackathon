from __future__ import annotations
from typing import Optional
import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status
from pydantic import ValidationError, BaseModel

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.validation import BenchmarkData, ListingValidationInput, ValidationResult, AIReviewSummary, HistoryListItem, KosReviewResponse
from app.services.db_service import fetch_latest_area_benchmark, save_validation_history, fetch_validation_history, fetch_validation_record_by_id
from app.services.gemini_service import (
    analyze_multimodal,
    generate_review_summary as gemini_generate_review_summary,
    generate_review_conclusion,
)
from app.services.aggregator_service import aggregate_area_benchmarks, extract_listing_from_url, discover_listings, fetch_mamikos_reviews
from app.services.validation_engine import calculate_trust_score

router = APIRouter(tags=["validation"])

class URLRequest(BaseModel):
    url: str

@router.post("/extract-url")
async def api_extract_url(request: URLRequest) -> dict:
    return await extract_listing_from_url(request.url)

@router.get("/discover")
async def api_discover_listings(area: str, limit: int = 10):
    return await discover_listings(area, limit)


def _parse_form_data(raw_json: Optional[str]) -> ListingValidationInput:
    if raw_json is None:
        raise AppError(
            "MISSING_FORM_DATA",
            "form_data must be provided as a JSON string.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    normalized_json = raw_json.strip().lstrip("\ufeff")
    if (
        len(normalized_json) >= 2
        and normalized_json[0] == normalized_json[-1]
        and normalized_json[0] in {"'", '"'}
    ):
        normalized_json = normalized_json[1:-1].strip().lstrip("\ufeff")
    try:
        return ListingValidationInput.model_validate_json(normalized_json)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(
            "INVALID_FORM_DATA",
            f"form_data must be valid JSON matching the listing validation schema: {exc}",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc


async def _read_chat_file(file: Optional[UploadFile]) -> str:
    if file is None:
        return ""

    filename = (file.filename or "").lower()
    if not filename.endswith(".txt"):
        raise AppError(
            "UNSUPPORTED_CHAT_FILE",
            "chat_file must be a .txt file.",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    raw = await file.read()
    return raw.decode("utf-8", errors="ignore")


async def _read_images(files: Optional[list[UploadFile]]) -> list[bytes]:
    settings = get_settings()
    if not files:
        return []
    if len(files) > settings.max_images:
        raise AppError("TOO_MANY_IMAGES", f"Upload at most {settings.max_images} images.")

    images: list[bytes] = []
    for file in files:
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise AppError(
                "UNSUPPORTED_IMAGE_FILE",
                "Every uploaded visual asset must be an image.",
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        raw = await file.read()
        if len(raw) > settings.max_image_bytes:
            raise AppError(
                "IMAGE_TOO_LARGE",
                f"Each image must be at most {settings.max_image_bytes} bytes.",
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        images.append(raw)
    return images


def _benchmark_or_none(raw: Optional[dict], area_name: str) -> Optional[BenchmarkData]:
    if raw is None:
        return None
    return BenchmarkData.model_validate({"area_name": area_name, **raw})


async def _benchmark_for_area(area_name: str) -> Optional[dict]:
    benchmark = await fetch_latest_area_benchmark(area_name)
    if benchmark is not None:
        return benchmark
    try:
        return await aggregate_area_benchmarks(area_name)
    except AppError:
        return None


@router.post("/validate-listing", response_model=ValidationResult)
async def validate_listing(
    background_tasks: BackgroundTasks,
    listing_data: Optional[str] = Form(default=None),
    chat_file: Optional[UploadFile] = File(default=None),
    images: Optional[list[UploadFile]] = File(default=None),
) -> ValidationResult:
    parsed_form = _parse_form_data(listing_data)

    chat_text, image_bytes_list = await asyncio.gather(
        _read_chat_file(chat_file),
        _read_images(images),
    )

    # Parallelize Benchmark and Multimodal AI Analysis
    benchmark_raw, analyses = await asyncio.gather(
        _benchmark_for_area(parsed_form.area_name),
        analyze_multimodal(chat_text, image_bytes_list, parsed_form.area_name)
    )
    chat_analysis, visual_analysis = analyses

    benchmark = _benchmark_or_none(benchmark_raw, parsed_form.area_name)
    result = calculate_trust_score(
        form_data=parsed_form,
        db_benchmark=benchmark,
        chat_analysis=chat_analysis,
        visual_analysis=visual_analysis,
    )

    red_flags = [a.title for a in result.detected_anomalies]
    conclusion = await generate_review_conclusion(
        risk_score=result.anomaly_score,
        red_flags=red_flags,
        facilities=parsed_form.room_facilities + parsed_form.shared_facilities,
    )
    result.conclusion_summary = conclusion

    record_id = await save_validation_history(
        {
            "form_data": parsed_form.model_dump(mode="json"),
            "benchmark": benchmark.model_dump(mode="json") if benchmark else None,
            "chat_analysis": chat_analysis,
            "visual_analysis": visual_analysis,
            "result": result.model_dump(mode="json"),
        }
    )
    result.record_id = record_id
    return result

from pydantic import BaseModel

class ReviewSummaryRequest(BaseModel):
    reviews: list[str]

@router.post("/review-summary", response_model=AIReviewSummary)
async def create_review_summary(request: ReviewSummaryRequest) -> AIReviewSummary:
    return await gemini_generate_review_summary(request.reviews)

@router.get("/history", response_model=list[HistoryListItem])
async def get_validation_history(device_id: str, limit: int = 20) -> list[HistoryListItem]:
    if not device_id:
        return []
    raw_records = await fetch_validation_history(device_id, limit)
    items = []
    for rec in raw_records:
        form = rec.get("form_data", {})
        res = rec.get("result", {})
        items.append(HistoryListItem(
            id=rec["id"],
            listing_name=form.get("listing_name", ""),
            area_name=form.get("area_name", ""),
            price=form.get("price", 0),
            anomaly_score=res.get("anomaly_score", 0),
            confidence_score=res.get("confidence_score", 100 - res.get("anomaly_score", 0)),
            status=res.get("status", ""),
            conclusion_summary=res.get("conclusion_summary", ""),
            image_url=form.get("image_url"),
            created_at=rec.get("created_at"),
        ))
    return items

@router.get("/history/{record_id}")
async def get_validation_record(record_id: str) -> dict:
    record = await fetch_validation_record_by_id(record_id)
    if not record:
        raise AppError("RECORD_NOT_FOUND", "History record not found", 404)
    return record

@router.get("/reviews/{kos_id}", response_model=KosReviewResponse)
async def get_kos_reviews(kos_id: str, limit: int = 10) -> KosReviewResponse:
    try:
        data = await fetch_mamikos_reviews(kos_id, limit)
        return KosReviewResponse(**data)
    except Exception as e:
        raise AppError("FETCH_REVIEWS_FAILED", f"Failed to fetch reviews: {str(e)}", 500)

