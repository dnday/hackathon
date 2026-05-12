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

    # Photos (Q1)
    if form_data.photos_provided == "Tidak":
        add_anomaly("No Photos Provided", "The listing does not provide photos.", 10)
    elif form_data.photos_provided == "Hanya foto saja":
        add_anomaly("Only Photos Provided", "The listing provides only photos, lacking video proof.", 5)

    # Map/Address (Q2)
    if form_data.specific_address_provided is False:
        add_anomaly("Vague Address", "No specific address is provided.", 10)

    # Name Matching (Q3 & Q4)
    if form_data.contact_name and form_data.bank_account_name:
        similarity = SequenceMatcher(None, form_data.contact_name.lower(), form_data.bank_account_name.lower()).ratio()
        if similarity < 0.4:
            add_anomaly("Name Mismatch", "Contact name and bank account name have low similarity.", 20)

    # Video Call/Survey (Q5)
    if not form_data.owner_willing_videocall:
        add_anomaly("Video Call Refused", "Owner is unwilling to verify the listing through a video call.", 30)

    # Urgency (Q6)
    if form_data.urgency_level == "Ya (harus transfer segera)":
        add_anomaly("High Urgency", "Owner demands immediate transfer.", 20)
    elif form_data.urgency_level == "Sedikit":
        add_anomaly("Slight Urgency", "Owner shows some urgency for payment.", 10)

    # Testimonials (Q7)
    if form_data.has_testimonials is False:
        add_anomaly("No Testimonials", "Listing has no previous testimonials.", 10)

    # Advanced Anomaly Detection: Price vs. Facilities
    premium_facilities = {"AC", "K. Mandi Dalam", "WiFi", "Air panas"}
    has_premium = any(facility in premium_facilities for facility in form_data.facilities)
    if has_premium and db_benchmark and db_benchmark.mean_price:
        if form_data.price < 0.6 * db_benchmark.mean_price:
            add_anomaly(
                "Too Good To Be True", 
                "The listing offers premium facilities but the price is significantly lower than the area benchmark.", 
                30
            )

    # AI Communication & Visual Analysis
    if visual.watermark_detected:
        add_anomaly("External Watermark Detected", "Images appear to contain logos or watermarks from another platform.", 40)
    
    pressure_points = min(30, round(chat.pressure_level * 0.3))
    if pressure_points > 0:
        add_anomaly("High-Pressure Communication", "Conversation shows urgency or pressure.", pressure_points)
        
    if chat.payment_anomaly_detected:
        add_anomaly("Payment Request Anomaly", "Unusual payment instructions or suspicious transfer pressure.", 15)

    if chat.inconsistencies_found:
        add_anomaly("Communication Inconsistencies", "Inconsistent claims or payment instructions.", 10)

    if not visual.room_interior_detected or not visual.realistic_images:
        add_anomaly("Visual Asset Mismatch", "Images do not clearly depict realistic room interiors.", 15)

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
        conclusion_summary="Pending..."
    )
