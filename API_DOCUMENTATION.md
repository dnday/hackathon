# KosCheck API Documentation & Integration Guide

Welcome to the KosCheck API Documentation. This document provides detailed technical information regarding the available endpoints, data schemas, risk scoring metrics, and cURL testing guides.

---

## Base URL
- **Local Environment**: `http://localhost:8000/api/v1`
- **Production Environment**: `https://<remote-server-ip>/api/v1`

---

## Risk Score Categorization

The AI validation engine calculates an `anomaly_score` for each requested listing based on a rigorous 9-point criteria.

- **0 - 30**: `SAFE` (Low Risk) - Green
- **31 - 60**: `WARNING` (Medium Risk) - Yellow
- **>= 61**: `DANGER` (High Risk) - Red

---

## Endpoint Overview

### 1. Deep Check (Validation Engine)
Performs deep hybrid validation combining rule-based heuristics and Gemini Multimodal AI reasoning.

- **URL**: `/validate-listing`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Fields**:
  - `form_data` (JSON String, Required): The 9-point QUICKCHECK data matrix.
  - `chat_file` (File, Optional): WhatsApp exported `.txt` chat log for psychological analysis.
  - `images` (Files, Optional): Screenshots of the property or testimonials for visual AI analysis.

### 2. Market Discovery (Explore)
Retrieves the latest property listings for a specific geographical area, utilizing our AES-128 scraping engine.

- **URL**: `/discover`
- **Method**: `GET`
- **Parameters**: 
  - `area` (string, required): Geographical target (e.g., "Depok").
  - `limit` (int, optional): Response limit (default: 5).

### 3. URL Extraction (Auto-Fill Scraper)
Extracts detailed property specifications directly from third-party URL platforms.

- **URL**: `/extract-url`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Payload**: `{"url": "string"}`

### 4. AI Review Summarization
Aggregates unformatted user reviews into structured, digestible bullet points.

- **URL**: `/review-summary`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Payload**: `{"reviews": ["string"]}`

---

## cURL Testing Guide

### 1. Test Deep Check Validation (High Risk Scenario)
Simulate a validation check against a suspicious property utilizing the updated 9-point QUICKCHECK schema:

```bash
curl -X POST "http://localhost:8000/api/v1/validate-listing" \
     -F 'form_data={
          "listing_name": "Kos Murah Banget Pusat Kota Mewah",
          "area_name": "Jakarta Selatan",
          "price": 300000,
          "owner_willing_videocall": false,
          "address_specificity": "HANYA AREA",
          "photos_match_location": "TIDAK",
          "info_consistency": "TIDAK",
          "dp_requested": true,
          "pressure_to_transfer": true,
          "recent_video_provided": "TIDAK",
          "payment_details_explained": "TIDAK DIJELASKAN",
          "fraud_history_found": true,
          "bank_account_name_match": "TIDAK",
          "room_facilities": ["AC", "K. Mandi Dalam"],
          "shared_facilities": ["WiFi"]
        }' | jq
```

### 2. Test Market Discovery (Scraper)
Fetch up to 5 properties in the Depok area:

```bash
curl -G "http://localhost:8000/api/v1/discover" \
     --data-urlencode "area=Depok" \
     --data-urlencode "limit=5" | jq
```

### 3. Test URL Extraction
Extract parameters natively from a Mamikos URL:

```bash
curl -X POST "http://localhost:8000/api/v1/extract-url" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://mamikos.com/room/kost-kabupaten-sleman-kost-campur-eksklusif-kost-singgahsini-pondok-garini-syariah-tipe-d-yogyakarta"}' | jq
```

### 4. Test AI Review Summary
Condense raw reviews:

```bash
curl -X POST "http://localhost:8000/api/v1/review-summary" \
     -H "Content-Type: application/json" \
     -d '{
           "reviews": [
             "Kos nyaman banget, AC dingin, WiFi kencang.",
             "Lokasi strategis dekat halte, tapi parkir sempit."
           ]
         }' | jq
```

---

## Interactive Testing via Swagger UI

KosCheck provides a built-in OpenAPI interactive interface.
1. Run the local server.
2. Open your browser and navigate to: `http://localhost:8000/docs`
3. Select an endpoint, click **"Try it out"**, construct your request, and click **"Execute"**.
