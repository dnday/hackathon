import asyncio
import json
from io import BytesIO
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from PIL import Image

from app.core.config import get_settings
from app.models.validation import CommunicationAnalysis, VisualAnalysis


CHAT_PROMPT = """
You are a property-listing validation analyst. Analyze the communication log for:
- high-pressure sales tactics
- sudden urgency
- inconsistent payment requests
- requests to pay outside a trusted platform

Return raw JSON only with this exact schema:
{
  "pressure_level": integer from 0 to 100,
  "inconsistencies_found": boolean,
  "payment_anomaly_detected": boolean,
  "urgency_detected": boolean,
  "summary": string
}
"""

VISUAL_PROMPT = """
You are a property-listing visual validation analyst. Analyze the uploaded images for:
- realistic room interiors
- non-room or unrelated images
- overlapping logos, screenshots, or watermarks from other platforms

Return raw JSON only with this exact schema:
{
  "room_interior_detected": boolean,
  "watermark_detected": boolean,
  "realistic_images": boolean,
  "summary": string
}
"""


def _safe_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    return json.loads(cleaned)


def _prepare_images(images: list[bytes]) -> list[Image.Image]:
    prepared: list[Image.Image] = []
    for raw in images:
        with Image.open(BytesIO(raw)) as image:
            prepared.append(image.convert("RGB").copy())
    return prepared


def _model() -> genai.GenerativeModel | None:
    settings = get_settings()
    api_key = settings.resolved_gemini_api_key
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=settings.gemini_model)


def _fallback_chat(summary: str) -> dict[str, Any]:
    return CommunicationAnalysis(
        pressure_level=0,
        inconsistencies_found=False,
        payment_anomaly_detected=False,
        urgency_detected=False,
        summary=summary,
    ).model_dump()


def _fallback_visual(summary: str, has_images: bool) -> dict[str, Any]:
    return VisualAnalysis(
        room_interior_detected=has_images,
        watermark_detected=False,
        realistic_images=has_images,
        summary=summary,
    ).model_dump()


async def analyze_communication_log(chat_text: str) -> dict[str, Any]:
    model = _model()
    if model is None:
        return _fallback_chat("Gemini API key is not configured; communication analysis skipped.")

    settings = get_settings()
    clipped_chat = chat_text[: settings.max_chat_chars]
    if not clipped_chat.strip():
        return _fallback_chat("No communication log was provided.")

    content = [CHAT_PROMPT, f"Communication log:\n{clipped_chat}"]
    try:
        response = await model.generate_content_async(
            content,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
            request_options={"timeout": 20},
        )
        return CommunicationAnalysis.model_validate(_safe_json(response.text)).model_dump()
    except (
        json.JSONDecodeError,
        ValueError,
        google_exceptions.ResourceExhausted,
        google_exceptions.TooManyRequests,
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
    ):
        return _fallback_chat("Communication analysis is temporarily unavailable.")


async def analyze_visual_assets(images: list[bytes]) -> dict[str, Any]:
    if not images:
        return _fallback_visual("No visual assets were provided.", has_images=False)

    model = _model()
    if model is None:
        return _fallback_visual("Gemini API key is not configured; visual analysis skipped.", True)

    try:
        image_parts = await asyncio.to_thread(_prepare_images, images)
        response = await model.generate_content_async(
            [VISUAL_PROMPT, *image_parts],
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
            request_options={"timeout": 25},
        )
        return VisualAnalysis.model_validate(_safe_json(response.text)).model_dump()
    except (
        json.JSONDecodeError,
        ValueError,
        google_exceptions.ResourceExhausted,
        google_exceptions.TooManyRequests,
        google_exceptions.ServiceUnavailable,
        google_exceptions.DeadlineExceeded,
        OSError,
    ):
        return _fallback_visual("Visual analysis is temporarily unavailable.", True)
