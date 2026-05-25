import httpx
import asyncio
import json

BASE_URL = "http://127.0.0.1:8001"

async def test_endpoints():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Testing GET /health")
        res = await client.get(f"{BASE_URL}/health")
        print(f"Status: {res.status_code}, Response: {res.text}\n")

        print("2. Testing GET /api/v1/discover")
        res = await client.get(f"{BASE_URL}/api/v1/discover", params={"area": "UGM Yogyakarta", "limit": 2})
        print(f"Status: {res.status_code}, Response Length: {len(res.text)}\n")

        print("3. Testing POST /api/v1/extract-url")
        payload = {"url": "https://mamikos.com/room/kost-sleman-kost-campur-murah-kost-mamirooms-cendrawasih-depok-sleman"}
        res = await client.post(f"{BASE_URL}/api/v1/extract-url", json=payload)
        print(f"Status: {res.status_code}, Response Length: {len(res.text)}\n")

        print("4. Testing POST /api/v1/review-summary")
        payload_rev = {"reviews": ["Tempatnya bagus banget", "Sayangnya sering mati listrik"]}
        res = await client.post(f"{BASE_URL}/api/v1/review-summary", json=payload_rev)
        print(f"Status: {res.status_code}, Response Length: {len(res.text)}\n")

        print("5. Testing POST /api/v1/validate-listing")
        form_data = {
            "listing_name": "Kost Mamirooms",
            "price": 1500000,
            "area_name": "UGM Yogyakarta",
            "room_facilities": ["AC", "Kasur"],
            "shared_facilities": ["WiFi"]
        }
        res = await client.post(f"{BASE_URL}/api/v1/validate-listing", data={"form_data": json.dumps(form_data)})
        print(f"Status: {res.status_code}, Response: {res.text}\n")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
