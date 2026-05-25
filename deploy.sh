#!/bin/bash
set -e

echo "🔄 Menarik update terbaru dari repository..."
git pull

if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "❌ Error: Docker Compose tidak ditemukan!"
    exit 1
fi

echo "📦 Membangun ulang dan me-restart container menggunakan $DOCKER_COMPOSE..."
$DOCKER_COMPOSE up -d --build

echo "✅ Deployment selesai! Backend sekarang berjalan dengan versi terbaru."
