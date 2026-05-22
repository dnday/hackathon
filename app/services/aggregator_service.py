from __future__ import annotations
import re
from statistics import mean, median
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
import json
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services.db_service import fetch_scraped_listing, save_market_benchmark, save_scraped_listings
from datetime import timezone, datetime, timedelta

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


def _parse_price(text: str) -> Optional[int]:
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
    last_error: Optional[Exception] = None

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

    premium_keywords = ["ac", "air panas", "water heater", "eksklusif", "premium", "vip"]
    premium_prices = []
    standard_prices = []
    for sample in samples:
        name_lower = sample["name"].lower()
        is_premium = any(kw in name_lower for kw in premium_keywords)
        if is_premium:
            premium_prices.append(sample["price"])
        else:
            standard_prices.append(sample["price"])

    payload = {
        "area_name": area_name,
        "mean_price": round(mean(prices), 2),
        "median_price": round(median(prices), 2),
        "mean_price_standard": round(mean(standard_prices), 2) if standard_prices else None,
        "mean_price_premium": round(mean(premium_prices), 2) if premium_prices else None,
        "sample_size": len(prices),
        "source": MAMIKOS_BASE_URL,
        "source_url": source_urls[0],
        "source_urls": source_urls,
        "sample_source": sample_source,
        "samples": samples[:50],
    }
    await save_market_benchmark(area_name, payload)
    return payload

async def extract_listing_from_url(url: str) -> dict[str, Any]:
    cached = await fetch_scraped_listing(url)
    if cached and "updated_at" in cached:
        updated_at = cached["updated_at"]
        if isinstance(updated_at, datetime):
            if datetime.now(timezone.utc) - updated_at < timedelta(days=14):
                return cached

    settings = get_settings()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.scraper_timeout_seconds),
        headers=headers,
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "EXTRACTION_FAILED",
                f"Failed to fetch URL: {str(exc)}",
                400,
            ) from exc
            
    html = response.text
    
    # Try to extract the JSON 'detail' object from the script tag
    detail = {}
    idx = html.find("var detail = {")
    if idx != -1:
        start = html.find("{", idx)
        depth = 0
        end = -1
        for i in range(start, len(html)):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            try:
                detail = json.loads(html[start:end])
            except Exception:
                pass

    if detail:
        listing_name = detail.get("room_title") or detail.get("name_slug") or "Extracted Listing"
        price = int(detail.get("price_monthly") or 0)
        
        # Mapping Mamikos keys to our schema
        room_raw = list(detail.get("fac_room", [])) + list(detail.get("fac_bath", []))
        shared_raw = list(detail.get("fac_share", [])) + list(detail.get("fac_park", []))
        
        # Simple normalization
        mapping = {
            "ac": "AC",
            "mandi dalam": "K. Mandi Dalam",
            "kasur": "Kasur",
            "lemari": "Lemari",
            "wifi": "WiFi",
            "parkir": "Parkir",
            "dapur": "Dapur",
            "air panas": "Air panas",
            "meja": "Meja",
            "kursi": "Kursi"
        }
        
        room_facilities = []
        for f in room_raw:
            f_low = f.lower()
            for key, val in mapping.items():
                if key in f_low and val not in room_facilities:
                    room_facilities.append(val)
                    
        shared_facilities = []
        for f in shared_raw:
            f_low = f.lower()
            for key, val in mapping.items():
                if key in f_low and val not in shared_facilities:
                    shared_facilities.append(val)

        result_data = {
            "listing_name": listing_name,
            "price": price,
            "room_facilities": room_facilities,
            "shared_facilities": shared_facilities,
            "listing_url": url,
        }
        await save_scraped_listings([result_data])
        return result_data

    # Fallback to old heuristic method
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "Extracted Listing"
    
    price = 0
    price_tags = soup.find_all(string=re.compile(r"Rp\s?[\d.]+"))
    for p in price_tags:
        parsed = _parse_price(p)
        if parsed:
            price = parsed
            break
            
    text_content = html.lower()
    room_facilities = []
    shared_facilities = []
    
    if "ac" in text_content: room_facilities.append("AC")
    if "mandi dalam" in text_content: room_facilities.append("K. Mandi Dalam")
    if "kasur" in text_content: room_facilities.append("Kasur")
    
    if "wifi" in text_content: shared_facilities.append("WiFi")

    result_data = {
        "listing_name": title,
        "price": price,
        "room_facilities": room_facilities,
        "shared_facilities": shared_facilities,
        "listing_url": url,
    }
    await save_scraped_listings([result_data])
    return result_data

async def discover_listings(area_name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search and discover listings for a specific area.
    Because search pages are heavily protected by JS, 
    this logic uses the aggregator logic to get URLs first,
    then scrapes the first few details for high quality data.
    """
    settings = get_settings()
    query = quote_plus(area_name)
    search_url = f"{MAMIKOS_BASE_URL}search?q={query}&sort=price%2Casc"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    room_urls = []
    # Fallback high-quality URLs for popular areas (Hackathon Demo Support)
    demo_fallbacks = {
        "depok": [
            "https://mamikos.com/room/kost-kabupaten-sleman-kost-campur-eksklusif-kost-singgahsini-pondok-garini-syariah-tipe-d-yogyakarta",
            "https://mamikos.com/room/kost-sleman-kost-putra-eksklusif-kost-singgahsini-rumah-tentrem-depok-sleman-yogyakarta",
            "https://mamikos.com/room/kost-sleman-kost-putri-murah-kost-singgahsini-puspita-depok-sleman",
        ],
        "ugm": [
            "https://mamikos.com/room/kost-sleman-kost-campur-murah-kost-mamirooms-cendrawasih-depok-sleman",
            "https://mamikos.com/room/kost-sleman-kost-putra-murah-kost-singgahsini-p-54-depok-sleman",
        ]
    }
    
    area_key = area_name.lower()
    for key, urls in demo_fallbacks.items():
        if key in area_key:
            room_urls.extend(urls)

    async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
        try:
            resp = await client.get(search_url)
            # Find all room links in the raw HTML using regex
            matches = re.findall(r'href="(/room/[^"]+)"', resp.text)
            for m in matches:
                full_url = f"https://mamikos.com{m.split('?')[0]}"
                if full_url not in room_urls:
                    room_urls.append(full_url)
        except Exception:
            pass

    # If regex failed, try a fallback area search pattern
    if not room_urls or len(room_urls) < 3:
        alt_search = f"https://mamikos.com/kost/kost-{area_name.lower().replace(' ', '-')}-murah"
        try:
            resp = await client.get(alt_search)
            matches = re.findall(r'href="(/room/[^"]+)"', resp.text)
            for m in matches:
                full_url = f"https://mamikos.com{m.split('?')[0]}"
                if full_url not in room_urls:
                    room_urls.append(full_url)
        except Exception:
            pass

    results = []
    # Scrape detail for the first N listings to get accurate info
    for url in room_urls[:limit]:
        try:
            data = await extract_listing_from_url(url)
            results.append(data)
        except Exception:
            continue
    
    # If we got results, they are high quality. We can use them to seed the benchmark and save to DB!
    if results:
        # Save listings to Firestore for the "Explore" feature
        await save_scraped_listings(results)
        
        prices = [r["price"] for r in results if r["price"] > 0]
        if prices:
            # Simple update to the benchmark logic (optional: can trigger full save_market_benchmark here)
            pass
            
    return results
