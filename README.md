# 🛡️ KosCheck Backend Engine

<div align="center">
  <p><strong>Advanced Asynchronous Fraud Detection API for Property Listings</strong></p>
  <p>
    Built with <strong>FastAPI</strong>, <strong>Google Gemini Multimodal AI</strong>, and <strong>Firebase Firestore</strong>.
  </p>
</div>

---

KosCheck is an enterprise-grade REST API designed to preemptively detect fraudulent rental property listings (boarding houses/apartments). It leverages a hybrid validation engine that combines strict deterministic rules (Pydantic) with advanced Multimodal LLM reasoning (Gemini Flash) to cross-validate visual assets, communication logs, and market pricing in real-time.

## 🚀 Core Architecture & Tech Stack

KosCheck is built for high concurrency and robust external integrations:

- **FastAPI (Python 3.11+)**: Asynchronous ASGI framework for non-blocking I/O.
- **Nginx & Uvicorn**: High-performance reverse proxy and application server.
- **Google Gemini AI**: Multimodal LLM to analyze WhatsApp chat psychology and property visuals.
- **Firebase Firestore**: NoSQL caching layer to reduce computational overhead and API rate limits.
- **Nominatim (OpenStreetMap)**: Geographic coordinate resolution for localized pricing.
- **PyCryptodome (AES-128 CBC)**: In-memory cryptographic engine to decrypt secured third-party payloads in real-time.
- **BeautifulSoup4 & HTTPX**: Asynchronous web scraping engine.

## ⚡ Performance Benchmarks

The infrastructure has been rigorously stress-tested using **Apache Benchmark (ab)** and **Locust** (simulating asynchronous User Journeys) on live remote servers.

| Metric | Result | Status |
|---|---|---|
| **API Latency (End-to-End)** | `13.6 seconds` | 🟢 Excellent |
| **Throughput Capacity** | `>114 req/s` | 🟢 Optimal |
| **Multimodal AI Inference** | `8.5 seconds` | 🟢 Fast |
| **AES-128 Decryption** | `<10 ms` | 🟢 Instant |
| **Scam Detection (Recall)** | `100%` | 🟢 Highly Reliable |

*Note: The AI algorithm utilizes a strict safety-bias, meaning it prefers triggering a False Positive (flagging a safe property as Medium Risk if information is lacking) rather than allowing a scam property to pass (False Negative).*

## 🧠 Fraud Validation Flow

1. **Input Reception**: Receives multipart data (listing JSON, chat logs `.txt`, and property photos).
2. **Parallel Processing (`asyncio`)**: Simultaneously executes:
   - Geocoding mapping via OpenStreetMap.
   - Price benchmark scraping from external APIs.
   - In-memory AES-128 payload decryption.
3. **AI Analysis**: Gemini AI extracts psychological urgency from chats and verifies image authenticity.
4. **Scoring Engine**: Combines all data into a 0-100 `anomaly_score`.
   - `0 - 30`: **SAFE** (Low Risk)
   - `31 - 60`: **WARNING** (Medium Risk)
   - `>= 61`: **DANGER** (High Risk)

---

## 💻 Local Setup & Deployment

1. **Initialize Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   ```
2. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Environment Configuration:**
   Copy `.env.example` to `.env` and configure:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-3-flash-preview
   FIREBASE_CREDENTIALS_PATH=./secrets/firebase-service-account.json
   CRON_API_KEY=your_strong_cron_key
   ```
4. **Run Server:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
5. **Access Swagger UI:**
   Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to test the API interactively.

## 📖 API Documentation

For detailed endpoint schemas, payload examples, and cURL testing guides, please refer to the [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## 📄 License

This project is licensed under the [MIT License](./LICENSE) - Copyright (c) 2026 GDGoC Hackathon Team.
