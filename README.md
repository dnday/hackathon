# KosCheck Backend

KosCheck adalah REST API berbasis FastAPI untuk validasi listing properti atau kamar sewa. API ini memeriksa konsistensi data listing, benchmark harga area, log komunikasi, dan aset visual menggunakan Firestore, Gemini API, serta agregasi data publik.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic v2
- Firebase Admin SDK dan Firestore
- Google Generative AI SDK
- httpx dan BeautifulSoup4
- Uvicorn

## Struktur Project

```text
app/
  api/v1/
    validation.py
    cron.py
  core/
    config.py
    exceptions.py
    firebase_init.py
  models/
    validation.py
  services/
    aggregator_service.py
    db_service.py
    firebase_db.py
    gemini_service.py
    validation_engine.py
  main.py
requirements.txt
```

## Setup Lokal

1. Buat virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependency.

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Buat file `.env` dari contoh.

```powershell
Copy-Item .env.example .env
```

4. Isi environment variable yang diperlukan.

```env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3-flash-preview
FIREBASE_CREDENTIALS_PATH=./secrets/firebase-service-account.json
CRON_API_KEY=your_strong_cron_key
```

5. Jalankan server.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

6. Buka dokumentasi API.

```text
http://127.0.0.1:8000/docs
```

## Environment Variables

| Name | Required | Description |
| --- | --- | --- |
| `GOOGLE_API_KEY` | Yes | API key untuk Gemini. Bisa juga pakai `GEMINI_API_KEY`. |
| `GEMINI_API_KEY` | Optional | Alternatif nama env untuk Gemini API key. |
| `GEMINI_MODEL` | Optional | Default: `gemini-3-flash-preview`. |
| `FIREBASE_CREDENTIALS_PATH` | Yes for Firestore | Path ke Firebase service account JSON. |
| `CRON_API_KEY` | Yes for cron | API key sederhana untuk endpoint cron. |

## Endpoint Utama

### `POST /api/v1/validate-listing`

Validasi listing dengan input `multipart/form-data`.

Fields:

- `form_data`: JSON string
- `chat_file`: file `.txt`, optional
- `images`: multiple image files, optional

Contoh `form_data`:

```json
{
  "listing_name": "Kos dekat UGM",
  "area_name": "UGM Yogyakarta",
  "price": 900000,
  "owner_willing_videocall": false,
  "contact_name": "Budi",
  "bank_account_name": "Budi",
  "listing_url": "https://example.com/listing/123"
}
```

Contoh request dengan `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/validate-listing" \
  -F 'form_data={"listing_name":"Kos dekat UGM","area_name":"UGM Yogyakarta","price":900000,"owner_willing_videocall":false}' \
  -F "chat_file=@chat.txt" \
  -F "images=@room-1.jpg" \
  -F "images=@room-2.jpg"
```

Response:

```json
{
  "anomaly_score": 25,
  "status": "SAFE",
  "detected_anomalies": [],
  "recommended_actions": [],
  "price_comparison": {
    "listing_price": 900000,
    "area_mean_price": null,
    "area_median_price": null,
    "difference_from_mean_percentage": null
  },
  "communication_analysis": {
    "pressure_level": 0,
    "inconsistencies_found": false,
    "payment_anomaly_detected": false,
    "urgency_detected": false,
    "summary": "..."
  },
  "visual_analysis": {
    "room_interior_detected": true,
    "watermark_detected": false,
    "realistic_images": true,
    "summary": "..."
  }
}
```

## Endpoint Cron

### `POST /api/v1/cron/update-benchmarks`

Endpoint ini dipakai external cron job untuk memperbarui benchmark harga area dari data publik.

Header:

```text
X-API-Key: your_strong_cron_key
```

Contoh:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/cron/update-benchmarks" \
  -H "X-API-Key: your_strong_cron_key"
```

Default area yang diambil adalah `UGM Yogyakarta`.

## Firestore Collections

API memakai dua collection:

- `market_benchmarks`: hasil agregasi benchmark harga area.
- `validation_history`: riwayat hasil validasi listing.

## Error Format

Semua error dikembalikan dengan format konsisten:

```json
{
  "error": true,
  "code": "ERROR_CODE",
  "message": "Human readable message"
}
```

## Verifikasi Cepat

```powershell
python -m compileall app
python -c "from app.main import app; print([route.path for route in app.routes])"
```

Health check:

```text
GET /health
```

Expected response:

```json
{"status": "ok"}
```
