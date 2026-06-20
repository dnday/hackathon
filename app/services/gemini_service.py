from __future__ import annotations
import asyncio
import json
from io import BytesIO
from typing import Any, Optional

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
    "ai_confidence_score": integer (0-100, how certain you are of this risk assessment),
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

Finally, analyze the sentiment of the reviews and give a numerical rating from 1 to 5 for the following categories: kebersihan, keamanan, fasilitas, lokasi, harga. 
MUST FOLLOW THIS STRICT GRADING RUBRIC FOR CONSISTENCY:
- 1: Highly negative, multiple complaints, terrible.
- 2: Mostly negative, some issues mentioned.
- 3: Neutral, average, OR the category is NOT mentioned at all.
- 4: Mostly positive, good experience.
- 5: Highly positive, excellent, highly praised.

Return raw JSON ONLY with this exact schema:
{
  "short_summary": "string",
  "positive_highlights": ["string", "string"],
  "negative_highlights": ["string", "string"],
  "topic_tags": ["string", "string"],
  "sentiment_scores": {
    "kebersihan": int (1-5),
    "keamanan": int (1-5),
    "fasilitas": int (1-5),
    "lokasi": int (1-5),
    "harga": int (1-5)
  }
}
"""

BATCH_SUMMARY_PROMPT = """
You are an AI assistant for a Kos (boarding house) discovery application.
You will be given a JSON list of Kos listings containing their name, price, address, and facilities.
For EACH listing, you must generate a short summary in Indonesian, strictly following this exact template structure:
"Kos [Name] berlokasi di [Short Address], ditawarkan dengan harga Rp[Price]/bulan. Fasilitas unggulannya meliputi [2-3 Top Facilities]. Kos ini sangat cocok untuk [Target User: e.g., mahasiswa, pekerja kantoran, pasutri, etc. based on facilities]."

Return ONLY a raw JSON array of strings. The array must have exactly the same length and order as the input list.
"""

REVIEW_COMPARE_PROMPT = """
You are a fraud investigator. Compare the user reviews against the claimed property facilities and price.
If the reviews strongly indicate the property doesn't match the claims (e.g. claims AC but reviews say no AC, or claims safe but reviews say it's a scam/fake), flag it.
Return raw JSON ONLY:
{
  "is_scam_suspected": boolean,
  "reason": "string explaining why or why not based on reviews vs claims"
}
"""

REVIEW_MODERATION_PROMPT = """
Kamu adalah sistem AI Content Moderator tingkat lanjut untuk "KosCheck", sebuah platform deteksi penipuan kos-kosan.
Tugas utama-mu adalah melindungi komunitas dari spam dan ujaran kebencian, SAMBIL TETAP MEMPERTAHANKAN informasi krusial terkait laporan penipuan.

=== ATURAN MODERASI KETAT ===

1. 🚨 PERLINDUNGAN DATA PENIPU (TIDAK DISENSOR):
   - Jika pengguna membagikan kontak (No HP, WhatsApp) atau rekening bank dalam konteks MEMBONGKAR PENIPUAN (contoh: "Penipu minta DP ke BCA 12345", "Awas nomor 08123 ini scammer").
   - TINDAKAN: BIARKAN 100%. Informasi ini adalah nyawa dari platform anti-scam.

2. 🛑 SPAM & HIJACKING LAPAK (DISENSOR / DITOLAK):
   - Jika pengguna membagikan kontak/link untuk tujuan promosi saingan, iklan kos lain, atau mencari penghuni (contoh: "Kos ini penuh, mending ke kos saya di 08...").
   - TINDAKAN: Sensor nomor/linknya menjadi "[DIHAPUS SISTEM]", atau tolak jika 100% isinya hanya iklan.

3. 🤬 UJARAN KEBENCIAN & KATA KASAR (DISENSOR):
   - Jika komentar mengandung makian kasar, rasisme, atau pelecehan.
   - TINDAKAN: Ganti kata kasarnya saja dengan "***". JANGAN menolak seluruh komentar jika inti pesannya (misal: melaporkan penipuan) valid dan berguna.

4. 🗑️ KONTEN BERBAHAYA / JUDI / PINJOL (DITOLAK MUTLAK):
   - Konten judi online, pinjaman online, pornografi, atau ancaman kekerasan fisik.
   - TINDAKAN: Tolak mutlak (is_approved: false).

KEMBALIKAN OUTPUT HANYA DALAM FORMAT JSON BERIKUT, TANPA TEKS LAIN (NO MARKDOWN BLOCKS):
{
  "is_approved": boolean, // false HANYA JIKA melanggar aturan No 4 atau komentar 100% murni spam iklan tak bermakna.
  "censored_content": "teks komentar akhir yang siap diposting (setelah sensor diterapkan, atau sama persis jika aman)",
  "reason": "Penjelasan singkat (1 kalimat) tentang apa yang disensor atau kenapa ditolak."
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

def _model() -> genai.Optional[GenerativeModel]:
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
        ai_confidence_score=0,
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

async def generate_batch_kos_summary(listings: list[dict]) -> list[str]:
    model = _model()
    default_summaries = ["Ringkasan AI tidak tersedia."] * len(listings)
    if not model or not listings:
        return default_summaries
        
    # Prepare minimal payload to save tokens
    payload = []
    for l in listings:
        payload.append({
            "name": l.get("listing_name"),
            "price": l.get("price"),
            "address": l.get("address"),
            "facilities": l.get("room_facilities", []) + l.get("shared_facilities", [])
        })
        
    prompt = f"{BATCH_SUMMARY_PROMPT}\n\nListings:\n{json.dumps(payload, indent=2)}"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        parsed = _safe_json(response.text)
        if isinstance(parsed, list):
            # Isi kekurangan rangkuman dengan default jika AI gagal memproses sebagian
            result = parsed[:len(listings)]
            while len(result) < len(listings):
                result.append("Ringkasan AI tidak tersedia.")
            return result
        return default_summaries
    except Exception as e:
        print(f"Batch summary failed: {e}")
        return default_summaries

async def compare_reviews_vs_claims(claims: dict, reviews: list[dict]) -> dict:
    model = _model()
    if not model:
        return {"is_scam_suspected": False, "reason": "AI offline (API Key belum dikonfigurasi di Vercel)."}
    if not reviews:
        return {"is_scam_suspected": False, "reason": "Kos ini belum memiliki ulasan, atau IP Vercel diblokir oleh Mamikos."}
        
    prompt = f"{REVIEW_COMPARE_PROMPT}\n\nKlaim:\n{json.dumps(claims, indent=2)}\n\nReviews:\n{json.dumps(reviews, indent=2)}"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return _safe_json(response.text)
    except Exception as e:
        return {"is_scam_suspected": False, "reason": f"Gagal menganalisis: {e}"}

async def moderate_user_comment(comment: str) -> dict:
    model = _model()
    if not model:
        return {"is_approved": True, "censored_content": comment, "reason": "AI offline"}
        
    prompt = f"{REVIEW_MODERATION_PROMPT}\n\nKomentar:\n{comment}"
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return _safe_json(response.text)
    except Exception as e:
        return {"is_approved": True, "censored_content": comment, "reason": f"Fallback error: {e}"}


