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
    benchmark: BenchmarkData | None,
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
    db_benchmark: BenchmarkData | None,
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

    # Photos
    if form_data.photos_provided == "Tidak":
        add_anomaly("No Photos Provided", "The listing does not provide photos.", 25)

    # Map/Address
    if form_data.specific_address_provided is False:
        add_anomaly("Vague Address", "No specific address is provided.", 30)

    # Bank Account Name Mismatch
    if getattr(form_data, "bank_account_name_match", True) is False:
        add_anomaly("Bank Name Mismatch", "Contact name does not match the bank account name.", 20)

    # Fraud History
    if getattr(form_data, "fraud_history_found", False) is True:
        add_anomaly("Fraud History", "The account or contact has a history of fraud.", 50)

    # Video Call/Survey
    if not form_data.owner_willing_videocall:
        add_anomaly("Video Call Refused", "Owner is unwilling to verify the listing through a video call.", 40)

    # Urgency
    if form_data.urgency_level == "Ya (harus transfer segera)":
        add_anomaly("High Urgency", "Owner demands immediate transfer.", 30)
    elif form_data.urgency_level == "Sedikit":
        add_anomaly("Slight Urgency", "Owner shows some urgency for payment.", 15)

    # Testimonials
    if form_data.has_testimonials is False:
        add_anomaly("No Testimonials", "Listing has no previous testimonials.", 10)

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
        "Verify the address and owner identity through an independent channel.",
        "Compare the listing price with nearby market benchmarks before payment.",
        "Keep screenshots, chat logs, and payment details for auditability.",
    ]
    if final_score >= 61:
        actions.insert(0, "Do not transfer before a direct on-site survey.")
    elif final_score >= 31:
        actions.insert(0, "Proceed only after successful video and payment-name validation.")
    else:
        actions.insert(0, "Listing data appears consistent, but complete normal verification.")

    return ValidationResult(
        anomaly_score=final_score,
        status=_status(final_score),
        detected_anomalies=anomalies,
        recommended_actions=actions,
        price_comparison=_price_comparison(form_data, db_benchmark),
        communication_analysis=chat,
        visual_analysis=visual,
        conclusion_summary="Pending..."
    )
