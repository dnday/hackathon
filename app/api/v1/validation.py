import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.validation import BenchmarkData, ListingValidationInput, ValidationResult
from app.services.db_service import fetch_latest_area_benchmark, save_validation_history
from app.services.gemini_service import analyze_communication_log, analyze_visual_assets
from app.services.aggregator_service import aggregate_area_benchmarks
from app.services.validation_engine import calculate_trust_score

router = APIRouter(tags=["validation"])


def _parse_form_data(raw_json: str | None) -> ListingValidationInput:
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


async def _read_chat_file(file: UploadFile | None) -> str:
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


async def _read_images(files: list[UploadFile] | None) -> list[bytes]:
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


def _benchmark_or_none(raw: dict | None, area_name: str) -> BenchmarkData | None:
    if raw is None:
        return None
    return BenchmarkData.model_validate({"area_name": area_name, **raw})


async def _benchmark_for_area(area_name: str) -> dict | None:
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
    form_data: str | None = Form(default=None),
    listing_data: str | None = Form(default=None),
    chat_file: UploadFile | None = File(default=None),
    whatsapp_chat_export: UploadFile | None = File(default=None),
    images: list[UploadFile] | None = File(default=None),
) -> ValidationResult:
    parsed_form = _parse_form_data(form_data or listing_data)

    chat_text, image_bytes = await asyncio.gather(
        _read_chat_file(chat_file or whatsapp_chat_export),
        _read_images(images),
    )

    benchmark_raw, chat_analysis, visual_analysis = await asyncio.gather(
        _benchmark_for_area(parsed_form.area_name),
        analyze_communication_log(chat_text),
        analyze_visual_assets(image_bytes),
    )

    benchmark = _benchmark_or_none(benchmark_raw, parsed_form.area_name)
    result = calculate_trust_score(
        form_data=parsed_form,
        db_benchmark=benchmark,
        chat_analysis=chat_analysis,
        visual_analysis=visual_analysis,
    )

    background_tasks.add_task(
        save_validation_history,
        {
            "form_data": parsed_form.model_dump(mode="json"),
            "benchmark": benchmark.model_dump(mode="json") if benchmark else None,
            "chat_analysis": chat_analysis,
            "visual_analysis": visual_analysis,
            "result": result.model_dump(mode="json"),
        },
    )
    return result
