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

## Penjelasan Backend

Backend KosCheck bertugas sebagai lapisan validasi listing kos sebelum user melakukan transaksi. Sistem menerima data listing, chat calon pemilik, dan gambar kamar, lalu menggabungkan beberapa sinyal risiko menjadi satu hasil penilaian.

### Alur Validasi

1. Client mengirim request ke `POST /api/v1/validate-listing` menggunakan `multipart/form-data`.
2. Backend membaca `form_data` sebagai JSON, lalu memvalidasi schema menggunakan Pydantic.
3. Jika ada file chat `.txt`, backend menganalisis isi percakapan dengan Gemini untuk mendeteksi tekanan, urgensi, inkonsistensi, atau anomali pembayaran.
4. Jika ada gambar, backend menganalisis aset visual dengan Gemini untuk mendeteksi apakah gambar terlihat realistis, menampilkan interior kamar, atau memiliki watermark dari platform lain.
5. Backend mengambil benchmark harga area dari Firestore. Jika belum ada, backend mencoba mengambil data publik melalui aggregator.
6. `validation_engine` menghitung `anomaly_score` dari gabungan harga, kesediaan video call, hasil analisis chat, dan hasil analisis visual.
7. Hasil validasi dikembalikan ke client dan disimpan ke Firestore sebagai riwayat.

### Komponen Utama

| Komponen | Fungsi |
| --- | --- |
| `app/main.py` | Entry point FastAPI, registrasi router, health check, dan error handler. |
| `app/api/v1/validation.py` | Endpoint validasi listing, parsing form, upload chat, upload gambar, dan orkestrasi service. |
| `app/api/v1/cron.py` | Endpoint cron untuk memperbarui benchmark harga area. |
| `app/models/validation.py` | Schema request dan response menggunakan Pydantic. |
| `app/services/validation_engine.py` | Rule engine untuk menghitung skor risiko dan rekomendasi tindakan. |
| `app/services/gemini_service.py` | Integrasi Gemini untuk analisis chat dan gambar. |
| `app/services/aggregator_service.py` | Agregasi data harga publik untuk benchmark area. |
| `app/services/db_service.py` | Operasi penyimpanan dan pembacaan data Firestore. |
| `app/core/config.py` | Konfigurasi environment variable. |

### Sinyal Risiko yang Dinilai

Backend saat ini menilai beberapa indikator utama:

- Harga listing jauh di bawah rata-rata area.
- Pemilik tidak bersedia melakukan video call.
- Chat mengandung tekanan tinggi, urgensi, atau instruksi pembayaran yang mencurigakan.
- Nama kontak dan pola komunikasi terindikasi tidak konsisten.
- Gambar tidak terlihat seperti interior kamar asli.
- Gambar memiliki watermark dari platform lain.
- Kombinasi beberapa sinyal lemah, misalnya harga terlalu murah dan pemilik menolak verifikasi langsung.

### Output Validasi

Response utama berupa:

- `anomaly_score`: skor risiko dari `0` sampai `100`.
- `status`: kategori hasil, yaitu `SAFE`, `WARNING`, atau `HIGH RISK`.
- `detected_anomalies`: daftar masalah yang ditemukan beserta poin risikonya.
- `recommended_actions`: saran aksi untuk user.
- `price_comparison`: perbandingan harga listing dengan benchmark area.
- `communication_analysis`: ringkasan hasil analisis chat.
- `visual_analysis`: ringkasan hasil analisis gambar.

## Saran Fitur Tambahan untuk v1

Fitur berikut cocok untuk versi v1 karena masih sejalan dengan arsitektur backend saat ini dan dapat meningkatkan nilai produk tanpa mengubah sistem secara besar-besaran.

### 1. Endpoint Detail Riwayat Validasi

Tambahkan endpoint untuk mengambil riwayat validasi dari Firestore.

- `GET /api/v1/validations`
- `GET /api/v1/validations/{validation_id}`

Manfaat:

- Frontend bisa menampilkan histori pengecekan user.
- Tim bisa melakukan audit hasil validasi.
- Data validasi bisa dipakai untuk evaluasi rule engine.

### 2. Risk Breakdown yang Lebih Transparan

Tambahkan breakdown skor per kategori.

Contoh kategori:

- `price_risk`
- `communication_risk`
- `visual_risk`
- `identity_risk`
- `verification_risk`

Manfaat:

- User lebih mudah memahami alasan listing dianggap aman atau berisiko.
- Frontend bisa membuat visualisasi skor yang lebih jelas.
- Debugging rule engine menjadi lebih mudah.

### 3. Area Benchmark Multi-Sumber

Perluas aggregator agar mengambil benchmark dari lebih dari satu sumber publik.

Manfaat:

- Benchmark harga lebih stabil.
- Mengurangi bias dari satu website.
- Meningkatkan kepercayaan terhadap hasil `price_comparison`.

### 4. Cache dan Expiry Benchmark

Tambahkan metadata seperti `expires_at` atau TTL untuk benchmark area.

Manfaat:

- Backend tidak perlu sering scraping ulang.
- Data lama bisa otomatis diperbarui.
- Response validasi menjadi lebih cepat.

### 5. Upload Limit Feedback

Tambahkan response yang lebih informatif saat gambar terlalu besar atau jumlah gambar terlalu banyak.

Manfaat:

- Frontend bisa menampilkan pesan error yang jelas.
- User tahu batas ukuran dan jumlah file.
- Mengurangi request gagal berulang.

### 6. Manual Review Flag

Tambahkan flag `requires_manual_review` pada response.

Contoh:

```json
{
  "requires_manual_review": true
}
```

Manfaat:

- Listing dengan risiko tinggi bisa diarahkan ke proses review manual.
- Frontend bisa menampilkan CTA seperti "Minta Bantuan Verifikasi".
- Cocok untuk MVP yang ingin tetap punya lapisan human-in-the-loop.

### 7. Basic API Key untuk Endpoint Validasi

Saat ini API key baru diterapkan pada endpoint cron. Untuk v1, endpoint validasi juga bisa diberi proteksi sederhana.

Manfaat:

- Mengurangi abuse dari pihak luar.
- Membatasi akses hanya dari frontend resmi.
- Lebih aman sebelum masuk ke auth user penuh.

### 8. Health Check Lebih Lengkap

Tambahkan endpoint readiness untuk mengecek koneksi Firebase dan konfigurasi Gemini.

Contoh:

- `GET /health`
- `GET /ready`

Manfaat:

- Deployment lebih mudah dipantau.
- Error konfigurasi bisa terdeteksi lebih cepat.
- Berguna untuk cloud platform atau CI/CD.

### 9. Test Case untuk Rule Engine

Tambahkan unit test untuk skenario risiko utama.

Contoh skenario:

- Harga normal dan data konsisten menghasilkan `SAFE`.
- Harga sangat murah dan video call ditolak menghasilkan `WARNING` atau `HIGH RISK`.
- Watermark dan tekanan chat tinggi menaikkan skor risiko.

Manfaat:

- Perubahan rule engine lebih aman.
- Skor risiko tidak berubah tanpa disadari.
- Cocok untuk menjaga kualitas saat fitur bertambah.

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
