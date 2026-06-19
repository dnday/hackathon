# Dokumentasi API Fitur Baru KosCheck (Anti-Scam & Validasi Lokasi)

Dokumen ini memuat detail *endpoint* REST API baru yang telah ditambahkan ke dalam sistem *backend* (`app/api/v1/validation.py`). Fitur-fitur ini difokuskan pada pengumpulan ulasan berbasis bukti dan deteksi anomali penipuan.

---

## 1. POST `/add-review`
**Deskripsi:** Mengunggah ulasan baru untuk sebuah kos-kosan dengan berlapiskan keamanan: Validasi lokasi ketat (Anti-Fake GPS) melalui metadata gambar, dan moderasi otomatis oleh AI (Anti-Spam & Sensor).
**Format Request:** `multipart/form-data`

### Body Parameters
| Parameter | Tipe | Keterangan |
| :--- | :--- | :--- |
| `kos_id` | `string` | ID unik kos-kosan (contoh: ID Mamikos). |
| `comment` | `string` | Teks ulasan atau laporan dari pengguna. |
| `user_lat` | `float` | Latitude posisi HP/Perangkat user saat ini. |
| `user_lon` | `float` | Longitude posisi HP/Perangkat user saat ini. |
| `kos_lat` | `float` | Latitude titik asli kos-kosan di peta. |
| `kos_lon` | `float` | Longitude titik asli kos-kosan di peta. |
| `photo` | `file` | Gambar bukti (Wajib memiliki EXIF GPS Metadata). |

### Aturan Validasi Internal:
1. **Verifikasi Fotografer:** Jarak EXIF GPS foto dengan `user_lat`/`user_lon` maksimal **1 KM**.
2. **Verifikasi Kehadiran di Kos:** Jarak EXIF GPS foto dengan `kos_lat`/`kos_lon` maksimal **500 Meter**.
3. **AI Moderation:** Konten ulasan akan difilter Gemini AI (Spam promosi otomatis ditolak dengan `HTTP 400`, kata kasar disensor menjadi `***`, sementara identitas rekening penipu dibiarkan tayang).

### Response (200 OK)
```json
{
  "status": "success",
  "message": "Komentar berhasil ditambahkan dan diverifikasi."
}
```

---

## 2. POST `/analyze-reviews`
**Deskripsi:** AI akan mengeksekusi "Cross-Examination" atau adu silang antara fasilitas kos yang diklaim (diiklankan) dengan kenyataan yang dialami pengguna dari seluruh rekam jejak ulasan. Sangat berguna untuk mendeteksi _Scam_ atau *False Advertising*.
**Format Request:** `application/json`

### Request Body
```json
{
  "kos_id": "12345678",
  "claims": {
    "fasilitas": ["AC", "Kolam Renang", "Aman"],
    "harga": 1500000
  }
}
```

### Response (200 OK)
```json
{
  "is_scam_suspected": true,
  "reason": "Ulasan pengguna secara eksplisit membantah adanya fasilitas AC dan menyebutkan ini adalah alamat fiktif."
}
```

---

## 3. POST `/review-summary` (Pembaruan Sentiment Scores)
**Deskripsi:** Menghasilkan ringkasan eksekutif dari banyak ulasan. Pembaruan terbaru kini menyertakan `sentiment_scores` berskala 1-5 secara ketat dan konsisten. Sangat cocok disalurkan ke komponen UI seperti *Radar Chart*.
**Format Request:** `application/json`

### Request Body
```json
{
  "reviews": [
    "Kos kotor banyak kecoa, tapi deket kampus. Harganya lumayan mahal tapi worth it lah. Ada CCTV."
  ]
}
```

### Response (200 OK)
```json
{
  "short_summary": "Kos ini memiliki keunggulan pada lokasi...",
  "positive_highlights": ["Lokasi strategis", "Ada CCTV"],
  "negative_highlights": ["Banyak kecoa", "Harga mahal"],
  "topic_tags": ["Kebersihan", "Lokasi", "Keamanan"],
  "sentiment_scores": {
    "kebersihan": 1,
    "keamanan": 5,
    "fasilitas": 3,
    "lokasi": 5,
    "harga": 4
  }
}
```
