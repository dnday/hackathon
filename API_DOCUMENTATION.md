# 🏠 KosCek API Documentation & Testing Guide

Selamat datang di dokumentasi API **KosCek**. Dokumen ini berisi detail teknis mengenai endpoint yang tersedia, skema data, serta panduan cara melakukan pengujian (testing).

---

## 🚀 Base URL
Lokal: `http://localhost:8000/api/v1`

---

## 🛠 Endpoint Overview

### 1. Deep Check (Validation Engine)
Menganalisis risiko penipuan listing kos menggunakan Rule-based scoring dan Gemini AI.
- **URL**: `/validate-listing`
- **Method**: `POST`
- **Type**: `multipart/form-data`
- **Fields**:
  - `listing_data` (JSON String): Data input utama.
  - `chat_file` (File, Optional): Export .txt chat WhatsApp.
  - `images` (Files, Optional): Screenshot kos/testimoni.

### 2. Auto-Fill dari URL (Scraper)
Mengekstrak data dari URL Mamikos secara akurat.
- **URL**: `/extract-url`
- **Method**: `POST`
- **Payload**: `{"url": "string"}`

### 3. Discover Listings (Explore)
Mencari daftar kos terbaru di suatu area (Hybrid Scraper + Seed Support).
- **URL**: `/discover`
- **Method**: `GET`
- **Params**: `area` (string), `limit` (int)

### 4. AI Review Summary
Merangkum kumpulan ulasan menjadi poin-poin terstruktur.
- **URL**: `/review-summary`
- **Method**: `POST`
- **Payload**: `{"reviews": ["string"]}`

---

## 🔍 Panduan Testing via Swagger UI

1. Buka browser dan akses: [http://localhost:8000/docs](http://localhost:8000/docs)
2. **Pilih Endpoint**: Klik pada salah satu baris endpoint (misal: `/discover`).
3. **Aktifkan Input**: Klik tombol **"Try it out"** di pojok kanan atas kotak.
4. **Isi Data**: Masukkan parameter atau JSON body sesuai contoh yang ada.
5. **Eksekusi**: Klik tombol biru **"Execute"**.
6. **Lihat Hasil**: Scroll ke bawah ke bagian "Server Response" untuk melihat JSON output.

---

## 💻 Panduan Testing via cURL

### 1. Test Fitur Discover (List Kos)
Mendapatkan 5 daftar kos di area Depok:
```bash
curl -G "http://localhost:8000/api/v1/discover" \
     --data-urlencode "area=Depok" \
     --data-urlencode "limit=5" | jq
```

### 2. Test Auto-Fill (Scraping Detail)
Mengekstrak data dari link Mamikos:
```bash
curl -X POST "http://localhost:8000/api/v1/extract-url" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://mamikos.com/room/kost-kabupaten-sleman-kost-campur-eksklusif-kost-singgahsini-pondok-garini-syariah-tipe-d-yogyakarta"}' | jq
```

### 3. Test Deep Check (High Risk Scenario)
Simulasi pengecekan kos yang mencurigakan (Anomali: No Photos, Fraud History, No Video Call):
```bash
curl -X POST "http://localhost:8000/api/v1/validate-listing" \
     -F 'listing_data={
          "listing_name": "Kos Murah Banget Mewah",
          "area_name": "Jakarta Selatan",
          "price": 300000,
          "owner_willing_videocall": false,
          "urgency_level": "Ya (harus transfer segera)",
          "photos_provided": "Tidak",
          "specific_address_provided": false,
          "has_testimonials": false,
          "fraud_history_found": true,
          "bank_account_name_match": false,
          "room_facilities": ["AC", "K. Mandi Dalam"],
          "shared_facilities": ["WiFi"]
        }' | jq
```

### 4. Test AI Review Summary
Merangkum ulasan kos:
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

## 📊 Kategori Skor Risiko
- **0 - 30**: `Low Risk` (Aman / Hijau)
- **31 - 60**: `Medium Risk` (Waspada / Kuning)
- **>= 61**: `High Risk` (Bahaya / Merah)

---
