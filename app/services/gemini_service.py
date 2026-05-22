from __future__ import annotations
import asyncio
import json
from io import BytesIO
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from PIL import Image

from app.core.config import get_settings
from app.models.validation import CommunicationAnalysis, VisualAnalysis, AIReviewSummary
from app.utils.metadata import get_image_metadata, format_metadata_for_prompt

# Unified Multimodal Prompt for high accuracy and low false positives
MULTIMODAL_ANALYSIS_PROMPT = """
You are a senior property fraud investigator. You will be provided with:
1. A communication log (chat) between a seeker and an owner.
2. Images uploaded of the property.
3. Technical metadata (EXIF) extracted from those images.

Your goal is to detect high-confidence fraud. You MUST avoid false positives.

Follow these strict rules:
- WATERMARKS: If you see a watermark from Mamikos, OLX, or similar, DO NOT assume it is a scam. It could be the legitimate owner cross-posting. Mention it as info only.
- CROSS-CHECK: Only flag "is_cross_check_fail" if there is a blatant physical impossibility (e.g., chat says 5th floor, photo is ground floor; chat says AC, photo shows only a fan; location metadata is in a different island/country than the claimed area).
- LINGUISTICS: Look for high-pressure tactics, sudden urgency, or bot-like testimonial patterns.

Return raw JSON only with this exact schema:
{
  "chat_analysis": {
    "ai_risk_score": integer (0-100),
    "pressure_level": integer (0-100),
    "inconsistencies_found": boolean,
    "payment_anomaly_detected": boolean,
    "urgency_detected": boolean,
    "bot_testimonial_detected": boolean,
    "is_cross_check_fail": boolean,
    "cross_check_details": string or null,
    "summary": string
  },
  "visual_analysis": {
    "room_interior_detected": boolean,
    "watermark_detected": boolean,
    "watermark_source": string or null,
    "realistic_images": boolean,
    "metadata_match_risk": integer (0-100 penalty for GPS/date mismatch),
    "metadata_summary": string or null,
    "summary": string
  }
}
"""

REVIEW_SUMMARY_PROMPT = """
You are a property review analyst. Summarize the following reviews into a structured format.
Extract the main positive highlights, negative highlights, and frequently mentioned topic tags (e.g., WiFi, Keamanan, Lokasi).
Also provide a short 1-2 sentence summary for a quick preview.

Return raw JSON only with this exact schema:
{
  "short_summary": string,
  "positive_highlights": array of strings,
  "negative_highlights": array of strings,
  "topic_tags": array of strings
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

async def analyze_multimodal(
    chat_text: str, 
    image_bytes_list: list[bytes], 
    area_name: str
) -> tuple[dict, dict]:
    model = _model()
    if not model:
        return _fallback_chat("AI not configured"), _fallback_visual("AI not configured", bool(image_bytes_list))
    
    # 1. Extract Metadata
    metadata_list = [get_image_metadata(b) for b in image_bytes_list]
    metadata_prompt = format_metadata_for_prompt(metadata_list)
    
    # 2. Build Content
    prompt = f"{MULTIMODAL_ANALYSIS_PROMPT}\n\nCLAIMED AREA: {area_name}\n\nCHAT LOG:\n{chat_text}\n\n{metadata_prompt}"
    
    content = [prompt]
    if image_bytes_list:
        content.extend(_prepare_images(image_bytes_list))
    
    try:
        response = await asyncio.to_thread(model.generate_content, content)
        parsed = _safe_json(response.text)
        return parsed["chat_analysis"], parsed["visual_analysis"]
    except Exception as e:
        return _fallback_chat(f"AI Analysis failed: {str(e)}"), _fallback_visual(f"AI Analysis failed: {str(e)}", bool(image_bytes_list))

def _fallback_chat(summary: str) -> dict[str, Any]:
    return CommunicationAnalysis(
        ai_risk_score=0,
        pressure_level=0,
        inconsistencies_found=False,
        payment_anomaly_detected=False,
        urgency_detected=False,
        bot_testimonial_detected=False,
        summary=summary,
    ).model_dump()

def _fallback_visual(summary: str, has_images: bool) -> dict[str, Any]:
    return VisualAnalysis(
        room_interior_detected=has_images,
        watermark_detected=False,
        realistic_images=has_images,
        summary=summary,
    ).model_dump()

async def generate_review_summary(reviews: list[str]) -> AIReviewSummary:
    model = _model()
    if not model:
        return AIReviewSummary(short_summary="Summary unavailable.", positive_highlights=[], negative_highlights=[], topic_tags=[])
    
    text_content = "\n\n".join(reviews)
    prompt = f"{REVIEW_SUMMARY_PROMPT}\n\nReviews:\n{text_content}"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return AIReviewSummary.model_validate(_safe_json(response.text))
    except Exception:
        return AIReviewSummary(short_summary="Failed to generate summary.", positive_highlights=[], negative_highlights=[], topic_tags=[])

async def generate_review_conclusion(risk_score: int, red_flags: list[str], facilities: list[str]) -> str:
    model = _model()
    if not model: return "Kesimpulan tidak tersedia."
    
    prompt = f"Kesimpulan: Kos ini memiliki skor risiko {risk_score}/100. Red flags: {', '.join(red_flags)}. Fasilitas: {', '.join(facilities)}. Buat kesimpulan 1 paragraf dalam bahasa Indonesia diawali 'Kesimpulan:'"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text.strip()
    except Exception:
        return "Gagal membuat kesimpulan."
