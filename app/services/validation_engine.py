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
    if score >= 60:
        return "HIGH RISK"
    if score >= 30:
        return "WARNING"
    return "SAFE"


def _price_comparison(
    form_data: ListingValidationInput,
    benchmark: BenchmarkData | None,
) -> PriceComparison:
    mean_price = benchmark.mean_price if benchmark else None
    median_price = benchmark.median_price if benchmark else None
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

    score = 0
    anomalies: list[DetectedAnomaly] = []

    def add_anomaly(title: str, description: str, points: int) -> None:
        nonlocal score
        score += points
        anomalies.append(
            DetectedAnomaly(title=title, description=description, points=points)
        )

    if db_benchmark and db_benchmark.mean_price and form_data.price < 0.6 * db_benchmark.mean_price:
        add_anomaly(
            "Price Far Below Market",
            "Listing price is below 60% of the current area mean.",
            30,
        )
    elif (
        db_benchmark
        and db_benchmark.mean_price
        and form_data.price < 0.8 * db_benchmark.mean_price
    ):
        add_anomaly(
            "Price Below Market",
            "Listing price is below 80% of the current area mean.",
            12,
        )

    if not form_data.owner_willing_videocall:
        add_anomaly(
            "Video Call Verification Refused",
            "Owner is unwilling to verify the listing through a video call.",
            25,
        )

    if visual.watermark_detected:
        add_anomaly(
            "External Watermark Detected",
            "Images appear to contain logos or watermarks from another platform.",
            40,
        )

    pressure_points = min(30, round(chat.pressure_level * 0.3))
    if pressure_points > 0:
        add_anomaly(
            "High-Pressure Communication",
            "Conversation shows urgency, pressure, or inconsistent payment behavior.",
            pressure_points,
        )

    if chat.payment_anomaly_detected:
        add_anomaly(
            "Payment Request Anomaly",
            "Conversation includes unusual payment instructions or suspicious transfer pressure.",
            15,
        )

    if chat.inconsistencies_found:
        add_anomaly(
            "Communication Inconsistencies",
            "Gemini detected inconsistent claims or payment instructions.",
            10,
        )

    if chat.urgency_detected and chat.pressure_level >= 50:
        add_anomaly(
            "Urgency Pattern Detected",
            "The communication pushes the user to decide or pay quickly.",
            5,
        )

    if not visual.room_interior_detected or not visual.realistic_images:
        add_anomaly(
            "Visual Asset Mismatch",
            "Images do not clearly depict realistic room interiors.",
            15,
        )

    if visual.watermark_detected and not form_data.owner_willing_videocall:
        add_anomaly(
            "Compounded Verification Risk",
            "Watermarked visual assets combined with refusal of live verification increases anomaly risk.",
            10,
        )

    if visual.watermark_detected and chat.pressure_level >= 70:
        add_anomaly(
            "Stolen-Asset Pressure Pattern",
            "External watermark appears together with high-pressure communication.",
            10,
        )

    if (
        db_benchmark
        and db_benchmark.mean_price
        and form_data.price < 0.6 * db_benchmark.mean_price
        and not form_data.owner_willing_videocall
    ):
        add_anomaly(
            "Underpriced Listing With Weak Verification",
            "The listing is far below market and the owner avoids video verification.",
            10,
        )

    final_score = min(score, 100)
    actions = [
        "Verify the address and owner identity through an independent channel.",
        "Compare the listing price with nearby market benchmarks before payment.",
        "Keep screenshots, chat logs, and payment details for auditability.",
    ]
    if final_score >= 60:
        actions.insert(0, "Pause the transaction until manual validation is complete.")
    elif final_score >= 30:
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
    )
