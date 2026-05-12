# KosCheck Backend System Logic & Features

Dokumen ini menjelaskan logika di balik sistem validasi "KosCheck", sistem *scoring* risiko, dan integrasi fitur yang ada di backend.

## 1. Ikhtisar Sistem (System Overview)
KosCheck adalah layanan backend berbasis **FastAPI** yang dirancang untuk menganalisis dan memvalidasi listing kos (indekos). Tujuannya adalah untuk mendeteksi potensi penipuan (scam) dengan menggabungkan:
1. Validasi data pengguna (kuesioner "Quick Check").
2. Perbandingan harga pasar (Benchmark Area).
3. Analisis AI (Google Gemini) pada bukti komunikasi (chat) dan aset visual (foto).

## 2. Fitur Utama Backend

- **Asynchronous API**: Dibangun menggunakan FastAPI untuk performa tinggi dengan proses non-blocking (async/await) saat memanggil database atau API eksternal.
- **Pydantic Data Validation**: Validasi input yang ketat menggunakan Pydantic (misalnya tipe data, *optional fields*, *legacy compatibility*).
- **Advanced Anomaly Detection**: Logika khusus yang menggabungkan faktor-faktor berbeda (seperti harga murah dipadukan dengan fasilitas premium) untuk menemukan pola penipuan tersembunyi.
- **Gemini AI Integration**: Memanfaatkan Google Gemini 3.1 Pro untuk:
  - Menganalisis *screenshot* atau riwayat *chat* WhatsApp untuk mendeteksi tekanan (*pressure*) atau anomali pembayaran.
  - Menganalisis gambar listing kos untuk mendeteksi *watermark* pihak ketiga atau gambar tidak realistis.
  - Membuat *summary* kesimpulan secara dinamis dalam bahasa manusia.
- **Background Tasks**: Menyimpan riwayat validasi secara *asynchronous* tanpa menghambat response ke pengguna (menggunakan `fastapi.BackgroundTasks`).

---

## 3. Logika Scoring & Rubrik (Risk Engine)

Sistem menggunakan poin penalti untuk menghitung skor anomali. **Semakin tinggi skor (0-100), semakin tinggi risiko penipuan.**

Proses ini berjalan di dalam file `app/services/validation_engine.py` pada fungsi `calculate_trust_score`.

### A. Evaluasi "Quick Check" (Berdasarkan Kuesioner Pengguna)
- **Q1 (Foto / Bukti Visual):**
  - Jika pengguna melaporkan "Tidak" ada foto: **+10 Poin**
  - Jika pengguna melaporkan "Hanya foto saja" (tidak ada video): **+5 Poin**
- **Q2 (Alamat Spesifik):**
  - Jika `specific_address_provided` bernilai False: **+10 Poin**
- **Q5 (Kesediaan Video Call):**
  - Jika pemilik menolak (`owner_willing_videocall` = False): **+30 Poin** (Indikasi risiko kritikal).
- **Q6 (Tingkat Urgensi):**
  - Jika "Ya (harus transfer segera)": **+20 Poin**
  - Jika "Sedikit" urgensi: **+10 Poin**
- **Q7 (Testimoni):**
  - Jika `has_testimonials` = False: **+10 Poin**

### B. Anomali Khusus: *Too Good To Be True*
Sistem membandingkan fasilitas yang diklaim dengan harga benchmark area:
- **Kondisi**: Jika listing menjanjikan fasilitas "Premium" (seperti `AC`, `K. Mandi Dalam`, `WiFi`, atau `Air panas`).
- **Kondisi**: DAN harga listing **kurang dari 60%** dari harga rata-rata (*mean price*) area tersebut.
- **Penalti**: **+30 Poin** (Indikasi kuat penipuan memancing korban dengan fasilitas mewah berharga sangat murah).

### C. Analisis AI (Chat & Visual)
Skor tambahan diberikan berdasarkan hasil analisis dari Gemini API:
- **Visual Watermark**: Jika Gemini mendeteksi ada *watermark* dari platform lain (misal Mamikos) di foto yang diunggah: **+40 Poin**.
- **Chat Pressure**: Jika ada tekanan dalam komunikasi, poin ditambahkan secara proporsional maksimal **+30 Poin**.
- **Payment Anomaly**: Indikasi rekening aneh atau perintah pembayaran di luar platform wajar: **+15 Poin**.
- **Inkonsistensi Komunikasi**: **+10 Poin**.
- **Aset Visual Tidak Realistis**: Foto tidak menunjukkan interior kamar kos yang wajar: **+15 Poin**.

### D. Penentuan Status Risiko
Setelah semua penalti dijumlahkan, skor maksimal dibatasi di **100**.
- **SAFE (Skor < 30)**: Indikasi aman, listing konsisten.
- **WARNING (Skor 30 - 59)**: Ada beberapa kejanggalan, perlu verifikasi manual (seperti *video call*).
- **HIGH RISK (Skor >= 60)**: Risiko penipuan sangat tinggi. Transaksi disarankan untuk segera dihentikan.

---

## 4. Kesimpulan AI Dinamis (Dynamic Conclusion)

Di luar penilaian skor statis, sistem mengompilasi kesimpulan berbentuk paragraf agar mudah dibaca pengguna akhir:
- **Fungsi**: `generate_review_conclusion` (di `gemini_service.py`).
- **Input**: Skor akhir, daftar kejanggalan (Red Flags), dan fasilitas yang ditawarkan.
- **Proses**: Gemini AI dipanggil dengan *prompt* khusus untuk merangkum hasil ini ke dalam satu paragraf pendek berbahasa Indonesia.
- **Syarat**: Paragraf wajib diawali dengan *"Kesimpulan: Kos ini memiliki..."*
- Teks ini dimasukkan ke dalam properti `conclusion_summary` pada respons API.

## 5. Alur Data (API Flow)
1. Klien mengirim data form, riwayat chat (opsional), dan foto (opsional) ke endpoint `POST /validate-listing`.
2. Data divalidasi oleh `ListingValidationInput`.
3. Tiga *task* berjalan secara paralel (`asyncio.gather`):
   - Mengambil data benchmark harga area dari database.
   - Mengirim chat ke Gemini untuk dianalisis tingkat tekanannya.
   - Mengirim gambar ke Gemini untuk mencari *watermark* atau gambar palsu.
4. Hasil dikumpulkan, diteruskan ke `calculate_trust_score` untuk dihitung anomali poinnya.
5. Memanggil Gemini untuk melakukan `generate_review_conclusion`.
6. Riwayat pemeriksaan dikirim ke *background task* untuk disimpan ke database.
7. `ValidationResult` (berisi skor, status, list anomali, tindakan rekomendasi, dan *summary*) dikembalikan sebagai respon JSON.
