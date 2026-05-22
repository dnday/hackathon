from __future__ import annotations
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ListingValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    listing_name: str = Field(..., min_length=2, max_length=180)
    area_name: str = Field(..., min_length=2, max_length=140)
    price: float = Field(..., gt=0)
    owner_willing_videocall: bool
    contact_name: str | None = Field(default=None, max_length=120)
    bank_account_name: str | None = Field(default=None, max_length=120)
    listing_url: str | None = Field(default=None, max_length=600)
    room_facilities: list[str] = Field(default_factory=list)
    shared_facilities: list[str] = Field(default_factory=list)
    urgency_level: str | None = Field(default=None, max_length=50)
    has_testimonials: bool | None = Field(default=None)
    photos_provided: str | None = Field(default=None, max_length=50)
    specific_address_provided: bool | None = Field(default=None)
    bank_account_name_match: bool | None = Field(default=None)
    fraud_history_found: bool = Field(default=False)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_field_names(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "area_name" not in data and "location_area" in data:
            data["area_name"] = data.pop("location_area")
        if "price" not in data and "price_per_month" in data:
            data["price"] = data.pop("price_per_month")
        if "contact_name" not in data and "input_contact_name" in data:
            data["contact_name"] = data.pop("input_contact_name")
        if "bank_account_name" not in data and "input_bank_account_name" in data:
            data["bank_account_name"] = data.pop("input_bank_account_name")
        return data

    @field_validator("contact_name", "bank_account_name", "listing_url")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BenchmarkData(BaseModel):
    model_config = ConfigDict(extra="allow")

    area_name: str
    mean_price: float | None = Field(default=None, ge=0)
    median_price: float | None = Field(default=None, ge=0)
    mean_price_standard: float | None = Field(default=None, ge=0)
    mean_price_premium: float | None = Field(default=None, ge=0)
    sample_size: int = Field(default=0, ge=0)
    source_url: str | None = None
    updated_at: datetime | None = None


class CommunicationAnalysis(BaseModel):
    ai_risk_score: int = Field(..., ge=0, le=100)
    pressure_level: int = Field(..., ge=0, le=100)
    inconsistencies_found: bool
    payment_anomaly_detected: bool
    urgency_detected: bool
    bot_testimonial_detected: bool
    is_cross_check_fail: bool = False
    cross_check_details: str | None = None
    summary: str = Field(..., min_length=1, max_length=2000)


class VisualAnalysis(BaseModel):
    room_interior_detected: bool
    watermark_detected: bool
    watermark_source: str | None = None
    realistic_images: bool
    metadata_match_risk: int = 0
    metadata_summary: str | None = None
    summary: str = Field(..., min_length=1, max_length=2000)


class DetectedAnomaly(BaseModel):
    title: str
    description: str
    points: int = Field(..., ge=0)


class PriceComparison(BaseModel):
    listing_price: float
    area_mean_price: float | None
    area_median_price: float | None
    difference_from_mean_percentage: float | None


class ValidationResult(BaseModel):
    anomaly_score: int = Field(..., ge=0, le=100)
    status: str
    detected_anomalies: list[DetectedAnomaly]
    recommended_actions: list[str]
    price_comparison: PriceComparison
    communication_analysis: CommunicationAnalysis
    visual_analysis: VisualAnalysis
    conclusion_summary: str


class AIReviewSummary(BaseModel):
    short_summary: str = Field(..., max_length=500)
    positive_highlights: list[str]
    negative_highlights: list[str]
    topic_tags: list[str]


class KosListing(BaseModel):
    name: str
    address: str
    coordinates: dict[str, float] | None = None
    price_per_month: float
    source: str
    description: str | None = None
    photos: list[str] = Field(default_factory=list)
    room_facilities: list[str] = Field(default_factory=list)
    shared_facilities: list[str] = Field(default_factory=list)
