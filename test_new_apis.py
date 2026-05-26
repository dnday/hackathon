import httpx
import asyncio
import json

BASE_URL = "http://127.0.0.1:8002"

async def test_endpoints():
    print("🚀 Starting Comprehensive API Tests 🚀\n")
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Test /health
        print("1️⃣  Testing GET /health")
        try:
            res = await client.get(f"{BASE_URL}/health")
            print(f"✅ Status: {res.status_code}")
            print(f"📄 Response: {res.text}\n")
        except Exception as e:
            print(f"❌ Failed: {e}\n")

        # 2. Test GET /api/v1/discover
        print("2️⃣  Testing GET /api/v1/discover (Area: UGM)")
        try:
            res = await client.get(f"{BASE_URL}/api/v1/discover", params={"area": "UGM Yogyakarta", "limit": 1})
            print(f"✅ Status: {res.status_code}")
            print(f"📄 Response Length: {len(res.text)} bytes")
            if res.status_code == 200:
                print(f"   Found {len(res.json())} listings\n")
        except Exception as e:
            print(f"❌ Failed: {e}\n")

        # 3. Test POST /api/v1/extract-url
        url_to_test = "https://mamikos.com/room/kost-kota-yogyakarta-kost-campur-eksklusif-kost-ndalem-mbak-yu-tipe-a-umbulharjo-yogyakarta-2"
        print("3️⃣  Testing POST /api/v1/extract-url")
        print(f"   URL: {url_to_test}")
        try:
            payload = {"url": url_to_test}
            res = await client.post(f"{BASE_URL}/api/v1/extract-url", json=payload)
            print(f"✅ Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Extracted Name: {data.get('listing_name')}")
                print(f"   Extracted Price: {data.get('price')}")
                print(f"   Extracted Source ID: {data.get('source_id')}\n")
            else:
                print(f"   Error: {res.text}\n")
        except Exception as e:
            print(f"❌ Failed: {e}\n")

        # 4. Test GET /api/v1/reviews/{kos_id}
        test_kos_id = "93056069"
        print(f"4️⃣  Testing GET /api/v1/reviews/{test_kos_id}")
        try:
            res = await client.get(f"{BASE_URL}/api/v1/reviews/{test_kos_id}", params={"limit": 2})
            print(f"✅ Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Overall Rating: {data.get('overall_rating')}")
                print(f"   Total Reviews: {data.get('total_reviews')}")
                print(f"   Sample Reviewer: {data.get('reviews')[0].get('name') if data.get('reviews') else 'None'}\n")
            else:
                print(f"   Error: {res.text}\n")
        except Exception as e:
            print(f"❌ Failed: {e}\n")

        # 5. Test POST /api/v1/validate-listing (Fraud Logic)
        print("5️⃣  Testing POST /api/v1/validate-listing")
        try:
            form_data = {
                "listing_name": "Kost Susah Sinyal",
                "price": 100000,
                "area_name": "UGM Yogyakarta",
                "owner_willing_videocall": False,
                "photos_provided": "Tidak",
                "specific_address_provided": False,
                "room_facilities": ["AC"],
                "shared_facilities": ["WiFi"]
            }
            res = await client.post(
                f"{BASE_URL}/api/v1/validate-listing", 
                data={"listing_data": json.dumps(form_data)}
            )
            print(f"✅ Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Anomaly Score: {data.get('anomaly_score')}")
                print(f"   Confidence Score: {data.get('confidence_score')}%")
                print(f"   Status: {data.get('status')}")
                print(f"   Detected Red Flags: {len(data.get('detected_anomalies', []))}\n")
            else:
                print(f"   Error: {res.text}\n")
        except Exception as e:
            print(f"❌ Failed: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
