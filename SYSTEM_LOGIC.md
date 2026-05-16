# KosCheck Backend System Logic & Features

Dokumen ini menjelaskan logika di balik sistem validasi "KosCheck", sistem *scoring* risiko, dan integrasi fitur yang ada di backend.

## 1. Ikhtisar Sistem (System Overview)
KosCheck adalah layanan backend berbasis **FastAPI** yang dirancang untuk menganalisis dan memvalidasi listing kos (indekos). Tujuannya adalah untuk mendeteksi potensi penipuan (scam) dengan menggabungkan:
1. Validasi data pengguna (kuesioner "Quick Check").
2. Perbandingan harga pasar dinamis (**Facility-Aware Benchmark**).
3. Analisis **AI Multimodal** (Google Gemini) pada bukti komunikasi (chat), aset visual (foto), dan **Metadata EXIF**.

## 2. Fitur Utama Backend

- **Multimodal AI Validation**: Menggunakan Google Gemini untuk menganalisis Chat, Gambar, dan Metadata secara bersamaan guna mendeteksi kontradiksi fisik (misal: deskripsi bilang lantai 5, foto terlihat lantai 1).
- **Facility-Aware Pricing**: Memisahkan benchmark harga area menjadi kategori "Standard" dan "Premium" (AC/Air Panas). Validasi harga dilakukan secara adil sesuai kelas fasilitas kos.
- **Deep Scraper & Auto-fill**: Mengekstrak data asli dari variabel JSON internal Mamikos untuk akurasi data 100% tanpa gangguan JavaScript frontend.
- **Automated Metadata Forensic**: Membaca data GPS dan Timestamp dari file foto asli untuk memverifikasi kebenaran lokasi kos.
- **AI Review Summary**: Merangkum kumpulan ulasan menjadi ringkasan singkat, highlight positif/negatif, dan tag topik otomatis.
- **Persistent Discovery**: Menyimpan setiap hasil pencarian kos ke dalam Firestore (`scraped_listings`) untuk memperkaya database lokal.

---

## 3. Logika Scoring & Rubrik (Risk Engine)

Sistem menggunakan formula gabungan:
**Final Score = (Rule Score × 0.6) + (AI Risk Score × 0.4)**
*Skor maksimal dibatasi 100.*

### A. Rule-Based Scoring (Quick Check)
| Kondisi | Penalti |
| --- | --- |
| Tidak ada foto/video | +25 |
| Alamat tidak spesifik / tidak bisa di-Maps | +30 |
| Nama kontak ≠ nama rekening bank | +20 |
| Nomor rekening/kontak memiliki riwayat penipuan | +50 |
| Pemilik tidak mau video call / tolak survei | +40 |
| Pemilik memaksa transfer segera | +30 |
| Ada urgensi ringan ("kamar terbatas") | +15 |
| Tidak ada testimoni pengguna sebelumnya | +10 |
| Harga terlalu murah vs benchmark kelasnya | +25 |

### B. AI Multimodal & Metadata (Cautious Detection)
Poin diberikan dengan hati-hati untuk menghindari *False Positive*:
- **Physical Inconsistency**: Kontradiksi fisik nyata antara chat vs foto: **+30 Poin**.
- **Metadata Mismatch**: Lokasi GPS foto melenceng jauh dari area: **Dinamis s/d +50 Poin**.
- **Fake Testimonials**: Pola linguistik bot/palsu: **+25 Poin**.
- **Platform Watermark**: Terdeteksi watermark platform lain: **+5 Poin** (Hanya informasi, bukan bukti kejahatan).

---

## 4. Penentuan Status Risiko
- **Low Risk (0 - 30)**: Aman, data konsisten.
- **Medium Risk (31 - 60)**: Waspada, perlu verifikasi video call & cek nama rekening.
- **High Risk (>= 61)**: Bahaya, jangan transfer sebelum survei langsung ke lokasi.

## 5. Alur Data (API Flow)
1. User memasukkan URL (Auto-fill) atau mengisi Form manual.
2. Backend melakukan ekstraksi metadata foto dan pengambilan benchmark area.
3. Chat, Foto, dan Metadata dikirim dalam satu prompt **Multimodal** ke Gemini.
4. `validation_engine` menghitung skor akhir berdasarkan formula bobot 60:40.
5. Hasil disimpan ke Firestore dan dikembalikan ke user sebagai laporan lengkap.
