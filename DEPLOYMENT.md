# Deployment Guide

Dokumen ini menjelaskan checklist deployment production untuk KosCheck Backend.

## Prasyarat

- Python 3.11+
- Firebase project dengan Firestore aktif
- Firebase service account JSON
- Gemini API key
- Runtime yang mendukung ASGI, misalnya Cloud Run, VM, container platform, atau server Linux dengan systemd

## Production Environment

Set environment variable berikut di platform deploy:

```env
ENVIRONMENT=production
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3-flash-preview
FIREBASE_CREDENTIALS_PATH=/app/secrets/firebase-service-account.json
CRON_API_KEY=replace_with_long_random_secret
```

Catatan:

- Jangan commit Firebase service account JSON.
- Gunakan secret manager platform jika tersedia.
- `CRON_API_KEY` harus panjang dan random karena melindungi endpoint update benchmark.

## Deploy Dengan Uvicorn

Untuk server sederhana:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Untuk production yang lebih kuat, jalankan di belakang process manager seperti systemd atau supervisor.

## Deploy Dengan Gunicorn

Install tambahan bila ingin memakai Gunicorn:

```bash
python -m pip install gunicorn
```

Jalankan:

```bash
gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

Rekomendasi awal:

- `workers`: mulai dari `2`, naikkan sesuai CPU dan traffic.
- `timeout`: minimal `120` karena request bisa menunggu Gemini API.
- Gunakan reverse proxy untuk TLS, rate limit, dan request size limit.

## Deploy Dengan Docker

Buat `Dockerfile` seperti ini bila dibutuhkan:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build:

```bash
docker build -t koscheck-backend .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/secrets:/app/secrets:ro" \
  koscheck-backend
```

## Cron Setup

Endpoint:

```text
POST /api/v1/cron/update-benchmarks
```

Header:

```text
X-API-Key: <CRON_API_KEY>
```

Contoh cron harian:

```bash
0 2 * * * curl -X POST "https://your-domain.com/api/v1/cron/update-benchmarks" -H "X-API-Key: your_strong_cron_key"
```

## Firestore Setup

Pastikan Firestore punya permission untuk service account yang dipakai backend.

Collections yang dipakai:

- `market_benchmarks`
- `validation_history`

Minimal permission IAM:

- Bisa membaca dokumen benchmark.
- Bisa menulis benchmark baru.
- Bisa menulis riwayat validasi.

## Health Check

Gunakan endpoint:

```text
GET /health
```

Expected response:

```json
{"status":"ok"}
```

## Operational Checklist

Sebelum go-live:

- `python -m compileall app` sukses.
- `/health` mengembalikan `200`.
- `/docs` tidak dibuka publik jika tidak diperlukan.
- Firebase credential sudah masuk secret manager.
- Gemini API key aktif dan punya quota.
- `CRON_API_KEY` sudah dikonfigurasi.
- Reverse proxy membatasi ukuran upload image.
- Log aplikasi dikirim ke log platform.
- Error response tetap memakai format standar.

## Troubleshooting

### Gemini analysis selalu fallback

Cek:

- `GOOGLE_API_KEY` atau `GEMINI_API_KEY` sudah benar.
- Model di `GEMINI_MODEL` tersedia untuk API key tersebut.
- Quota Gemini tidak habis.

### Benchmark selalu kosong

Cek:

- Cron endpoint sudah dipanggil.
- `CRON_API_KEY` benar.
- Firestore credentials valid.
- Collection `market_benchmarks` terisi.

### Firestore tidak menyimpan history

Cek:

- `FIREBASE_CREDENTIALS_PATH` mengarah ke file yang benar.
- Service account punya permission tulis.
- Runtime dapat membaca file credential.

### Upload ditolak

Cek:

- File chat harus `.txt`.
- File visual harus punya content type `image/*`.
- Jumlah image tidak lebih dari konfigurasi `max_images`.
- Ukuran tiap image tidak melebihi `max_image_bytes`.
