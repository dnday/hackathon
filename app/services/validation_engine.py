from __future__ import annotations
from typing import Optional
from app.models.validation import (
    BenchmarkData,
    CommunicationAnalysis,
    DetectedAnomaly,
    ListingValidationInput,
    PriceComparison,
    ValidationResult,
    VisualAnalysis,
)


def _status(score: int) -> str:
    if score >= 61:
        return "High Risk"
    if score >= 31:
        return "Medium Risk"
    return "Low Risk"


def _price_comparison(
    form_data: ListingValidationInput,
    benchmark: Optional[BenchmarkData],
) -> PriceComparison:
    mean_price = benchmark.mean_price if benchmark else None
    median_price = benchmark.median_price if benchmark else None

    if benchmark:
        premium_facilities = {"AC", "K. Mandi Dalam", "Air panas", "Eksklusif"}
        has_premium = any(
            f in premium_facilities for f in form_data.room_facilities + form_data.shared_facilities
        )
        if has_premium and benchmark.mean_price_premium:
            mean_price = benchmark.mean_price_premium
        elif not has_premium and benchmark.mean_price_standard:
            mean_price = benchmark.mean_price_standard

    difference = None
    if mean_price and mean_price > 0:
        difference = round(((form_data.price - mean_price) / mean_price) * 100, 2)

    return PriceComparison(
        listing_price=form_data.price,
        area_mean_price=mean_price,
        area_median_price=median_price,
        difference_from_mean_percentage=difference,
    )


def calculate_trust_score(
    form_data: ListingValidationInput,
    db_benchmark: Optional[BenchmarkData],
    chat_analysis: CommunicationAnalysis | dict,
    visual_analysis: VisualAnalysis | dict,
) -> ValidationResult:
    chat = (
        chat_analysis
        if isinstance(chat_analysis, CommunicationAnalysis)
        else CommunicationAnalysis.model_validate(chat_analysis)
    )
    visual = (
        visual_analysis
        if isinstance(visual_analysis, VisualAnalysis)
        else VisualAnalysis.model_validate(visual_analysis)
    )

    rule_score = 0
    anomalies: list[DetectedAnomaly] = []

    def add_anomaly(title: str, description: str, points: int) -> None:
        nonlocal rule_score
        rule_score += points
        anomalies.append(
            DetectedAnomaly(title=title, description=description, points=points)
        )

    # 1. Address Specificity
    if form_data.address_specificity == "HANYA AREA":
        add_anomaly("Vague Address", "No specific address is provided, only general area.", 25)
    elif form_data.address_specificity == "HANYA ALAMAT":
        add_anomaly("Address Unverifiable", "Address is provided but cannot be found on maps.", 15)

    # 2. Photos Match Location
    if form_data.photos_match_location == "TIDAK":
        add_anomaly("Fake Photos", "Photos provided do not match the actual location.", 45)
    elif form_data.photos_match_location == "BELUM BISA DIPASTIKAN":
        add_anomaly("Unverified Photos", "Unable to confirm if photos belong to the property.", 10)

    # 3. Information Consistency
    if form_data.info_consistency == "TIDAK":
        add_anomaly("Inconsistent Information", "Information about facilities, rules, or price changed during communication.", 20)

    # 4. Video Call / Survey
    if not form_data.owner_willing_videocall:
        add_anomaly("Video Call Refused", "Owner is unwilling to verify the listing through a video call.", 30)

    # 5. DP Requested
    if form_data.dp_requested:
        add_anomaly("DP Requested Early", "Owner asked for a down payment upfront.", 15)

    # 6. Pressure to Transfer (Urgency/FOMO)
    if form_data.pressure_to_transfer:
        add_anomaly("High Urgency (FOMO)", "Owner demands immediate transfer by claiming rooms are running out.", 35)

    # 7. Recent Video Provided
    if form_data.recent_video_provided == "TIDAK":
        add_anomaly("Refused Recent Video", "Owner refused to send a recent video of the property.", 25)
    elif form_data.recent_video_provided == "HANYA VIDEO LAMA":
        add_anomaly("Old Video Only", "Owner only provided old videos.", 15)

    # 8. Bank Account Match
    if form_data.bank_account_name_match == "TIDAK":
        add_anomaly("Bank Name Mismatch", "Contact name does not match the bank account name.", 35)
    elif form_data.bank_account_name_match == "TIDAK TAHU":
        add_anomaly("Bank Name Unknown", "Cannot verify if bank account matches the contact identity.", 15)

    # 9. Payment Details Explained
    if getattr(form_data, "payment_details_explained", "") == "TIDAK DIJELASKAN":
        add_anomaly("Blind Transfer Request", "Owner asks for transfer without explaining price details/rules.", 30)
    elif getattr(form_data, "payment_details_explained", "") == "SEBAGIAN DIJELASKAN":
        add_anomaly("Vague Payment Terms", "Payment details are partially explained but missing key info.", 10)

    # Fraud History Check
    if getattr(form_data, "fraud_history_found", False) is True:
        add_anomaly("Fraud History", "The account or contact has a history of fraud.", 50)

    # Price vs. Benchmark
    if db_benchmark:
        premium_facilities = {"AC", "Air panas", "Eksklusif", "Premium", "VIP"}
        has_premium = any(
            f in premium_facilities for f in form_data.room_facilities + form_data.shared_facilities
        )
        target_benchmark = db_benchmark.mean_price
        if has_premium and db_benchmark.mean_price_premium:
            target_benchmark = db_benchmark.mean_price_premium
        elif not has_premium and db_benchmark.mean_price_standard:
            target_benchmark = db_benchmark.mean_price_standard

        if target_benchmark and target_benchmark > 0:
            if form_data.price < 0.6 * target_benchmark:
                add_anomaly(
                    "Too Good To Be True", 
                    "The listing price is significantly lower than the area benchmark for its class.", 
                    25
                )

    # AI Multimodal & Metadata Analysis (CAUTIOUS LOGIC)
    if visual.metadata_match_risk > 0:
        add_anomaly("Metadata Mismatch", visual.metadata_summary or "Technical metadata does not match the claimed listing info.", visual.metadata_match_risk)

    if chat.is_cross_check_fail:
        add_anomaly("Physical Inconsistency", chat.cross_check_details or "Blatant mismatch between description and visual evidence.", 30)

    if visual.watermark_detected:
        # LOW penalty for watermarks to avoid false positives (cross-posting)
        add_anomaly("Platform Watermark", f"Image contains a watermark from {visual.watermark_source or 'another platform'}. Verify if the owner is cross-posting.", 5)
    
    if chat.bot_testimonial_detected:
        add_anomaly("Fake Testimonials", "AI detected potential bot or fake testimonials patterns.", 25)

    if chat.payment_anomaly_detected:
        add_anomaly("Payment Request Anomaly", "Unusual or risky payment instructions detected in chat.", 20)

    if chat.pressure_level > 70:
        add_anomaly("High-Pressure Sales", "AI detected aggressive pressure to transfer money immediately.", 20)

    # Final Score Calculation
    ai_risk_score = chat.ai_risk_score
    final_score = min(100, round((rule_score * 0.6) + (ai_risk_score * 0.4)))

    actions = [
        "Verifikasi alamat dan identitas pemilik melalui jalur independen.",
        "Bandingkan harga dengan standar pasar di sekitar sebelum membayar.",
        "Simpan bukti percakapan, tangkapan layar, dan detail pembayaran.",
    ]
    if final_score >= 61:
        actions.insert(0, "Berisiko tinggi, jangan bayar sebelum benar-benar terverifikasi")
    elif final_score >= 31:
        actions.insert(0, "Perlu waspada dan verifikasi tambahan sebelum membayar.")
    else:
        actions.insert(0, "Aman, tetapi tetap lakukan pengecekan akhir.")

    # Extremity & Consistency Confidence Score
    # 1. Base Confidence (Distance from 50)
    base_confidence = abs(final_score - 50) * 2

    # 2. Evidence Bonuses
    bonus_confidence = 0
    if db_benchmark and db_benchmark.sample_size > 10:
        bonus_confidence += 10
    if form_data.photos_provided != "Tidak":
        bonus_confidence += 10

    final_confidence = min(100, base_confidence + bonus_confidence)

    return ValidationResult(
        anomaly_score=final_score,
        confidence_score=final_confidence,
        status=_status(final_score),
        detected_anomalies=anomalies,
        recommended_actions=actions,
        price_comparison=_price_comparison(form_data, db_benchmark),
        communication_analysis=chat,
        visual_analysis=visual,
        conclusion_summary="Pending..."
    )
