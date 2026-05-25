#!/bin/bash
set -e

echo "🔄 Menarik update terbaru dari repository..."
git pull

echo "📦 Membangun ulang dan me-restart container menggunakan Docker Compose..."
docker compose up -d --build

echo "✅ Deployment selesai! Backend sekarang berjalan dengan versi terbaru."
