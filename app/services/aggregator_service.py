import re
from statistics import mean, median
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services.db_service import save_market_benchmark

MAMIKOS_BASE_URL = "https://mamikos.com/"
DEFAULT_AREA = "UGM Yogyakarta"
UGM_YOGYAKARTA_URL = (
    "https://mamikos.com/kost/kost-dekat-ugm-murah?sort=price%2Casc"
)
PRICE_PATTERNS = [
    re.compile(r"Harga\s*Sewa\s*:\s*([\d.]{5,})", re.IGNORECASE),
    re.compile(r"Rp\s?([\d.]{5,})", re.IGNORECASE),
]
MIN_MONTHLY_PRICE = 200_000
MAX_MONTHLY_PRICE = 20_000_000
UGM_STATIC_MAMIKOS_SAMPLES = [
    {"name": "Kost Eksklusif Dekat UGM", "price": 1_520_000},
    {"name": "Kost Asrama Pertiwi 5 Tipe Executive Mlati Yogyakarta", "price": 1_500_000},
    {"name": "Kost Wisma Yudhistira Tipe B Mlati Sleman Yogyakarta", "price": 1_680_000},
    {"name": "Kost Adenium Dekat UGM Tipe AC Sendowo Mlati Sleman Yogyakarta", "price": 1_800_000},
]
AREA_FALLBACK_MEANS = {
    "ugm": 1_625_000,
    "yogyakarta": 1_250_000,
    "jogja": 1_250_000,
    "sleman": 1_350_000,
    "bandung": 1_600_000,
    "jakarta": 2_500_000,
    "depok": 1_500_000,
    "surabaya": 1_700_000,
    "malang": 1_100_000,
    "semarang": 1_300_000,
    "solo": 1_050_000,
    "surakarta": 1_050_000,
    "denpasar": 1_800_000,
}


def _parse_price(text: str) -> int | None:
    for pattern in PRICE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        try:
            price = int(match.group(1).replace(".", ""))
        except ValueError:
            continue
        if MIN_MONTHLY_PRICE <= price <= MAX_MONTHLY_PRICE:
            return price
    return None


def _source_urls(area_name: str) -> list[str]:
    normalized_area = area_name.casefold()
    urls: list[str] = []
    if "ugm" in normalized_area and (
        "yogyakarta" in normalized_area or "jogja" in normalized_area
    ):
        urls.append(UGM_YOGYAKARTA_URL)

    query = quote_plus(area_name)
    urls.append(f"{MAMIKOS_BASE_URL}search?q={query}&sort=price%2Casc")
    return list(dict.fromkeys(urls))


def _is_ugm_yogyakarta(area_name: str) -> bool:
    normalized_area = area_name.casefold()
    return "ugm" in normalized_area and (
        "yogyakarta" in normalized_area or "jogja" in normalized_area
    )


def _fallback_samples_for_area(area_name: str) -> list[dict[str, Any]]:
    normalized_area = area_name.casefold()
    if _is_ugm_yogyakarta(area_name):
        return UGM_STATIC_MAMIKOS_SAMPLES

    matched_mean = next(
        (price for key, price in AREA_FALLBACK_MEANS.items() if key in normalized_area),
        None,
    )
    if matched_mean is None:
        matched_mean = 1_400_000

    low = round(matched_mean * 0.85 / 50_000) * 50_000
    high = round(matched_mean * 1.15 / 50_000) * 50_000
    return [
        {"name": f"Kost ekonomis sekitar {area_name}", "price": int(low)},
        {"name": f"Kost standar sekitar {area_name}", "price": int(matched_mean)},
        {"name": f"Kost nyaman sekitar {area_name}", "price": int(high)},
    ]


def _extract_price_samples(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    samples: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    def add_sample(title: str, price: int) -> None:
        title = " ".join(title.split())
        if not title:
            return
        key = (title, price)
        if key in seen:
            return
        seen.add(key)
        samples.append({"name": title, "price": price})

    def scoped_heading_text(heading: Any) -> str:
        parts = [heading.get_text(" ", strip=True)]
        for sibling in heading.find_next_siblings(limit=8):
            if getattr(sibling, "name", None) in {"h1", "h2", "h3", "h4"}:
                break
            parts.append(sibling.get_text(" ", strip=True))
        return " ".join(" ".join(parts).split())

    for heading in soup.find_all(["h2", "h3", "h4"]):
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title:
            continue

        nearby_text = scoped_heading_text(heading)
        price = _parse_price(nearby_text)
        if price is None:
            continue

        add_sample(title, price)

    for element in soup.find_all(["article", "section", "li", "div"]):
        text = " ".join(element.get_text(" ", strip=True).split())
        if "Rp" not in text and "Harga Sewa" not in text:
            continue

        price = _parse_price(text)
        if price is None:
            continue

        title_node = element.find(["h1", "h2", "h3", "h4", "a"])
        title = title_node.get_text(" ", strip=True) if title_node else text[:120]
        add_sample(title, price)

    return samples


async def aggregate_area_benchmarks(area_name: str = DEFAULT_AREA) -> dict[str, Any]:
    settings = get_settings()
    headers = {"User-Agent": settings.scraper_user_agent}
    source_urls = _source_urls(area_name)
    samples: list[dict[str, Any]] = []
    last_error: Exception | None = None

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.scraper_timeout_seconds),
        headers=headers,
        follow_redirects=True,
    ) as client:
        for source_url in source_urls:
            try:
                response = await client.get(source_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            samples = _extract_price_samples(response.text)
            if samples:
                break

    sample_source = "live_html"
    if not samples:
        samples = _fallback_samples_for_area(area_name)
        sample_source = "area_estimate_fallback"

    if not samples and last_error:
        raise AppError(
            "AGGREGATOR_UPSTREAM_ERROR",
            "Unable to fetch public rental benchmark data.",
            502,
        ) from last_error

    prices = [sample["price"] for sample in samples]
    if not prices:
        raise AppError(
            "AGGREGATOR_NO_PRICE_SAMPLES",
            f"No rental price samples were found for {area_name}.",
            502,
        )

    payload = {
        "area_name": area_name,
        "mean_price": round(mean(prices), 2),
        "median_price": round(median(prices), 2),
        "sample_size": len(prices),
        "source": MAMIKOS_BASE_URL,
        "source_url": source_urls[0],
        "source_urls": source_urls,
        "sample_source": sample_source,
        "samples": samples[:50],
    }
    await save_market_benchmark(area_name, payload)
    return payload
