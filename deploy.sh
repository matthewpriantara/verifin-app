#!/usr/bin/env bash
set -e

# Pindah ke direktori root repository
cd "$(dirname "$0")"

# 1. Ambil Git Commit Hash & Timestamp
export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
export BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=========================================================="
echo "🚀 Verifin Production Deploy"
echo "   Commit : ${GIT_COMMIT}"
echo "   Time   : ${BUILD_TIME}"
echo "=========================================================="

# Opsi --pull untuk auto git pull sebelum build
if [ "$1" == "--pull" ] || [ "$1" == "-p" ]; then
    echo "📥 Menarik kode terbaru dari origin main..."
    git -c http.version=HTTP/1.1 pull origin main
    export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
    echo "   Commit terbaru: ${GIT_COMMIT}"
fi

# 2. Build Container dengan metadata commit
echo "🔨 Membangun container Docker dengan metadata commit..."
docker compose build \
    --build-arg GIT_COMMIT="${GIT_COMMIT}" \
    --build-arg BUILD_TIME="${BUILD_TIME}"

# 3. Jalankan container
echo "▶️  Menjalankan container terbaru..."
docker compose up -d

echo "=========================================================="
echo "✅ Deploy Berhasil!"
echo "   Backend Health: http://localhost:8019/api/v1/health"
echo "   Frontend      : http://localhost:3019"
echo "=========================================================="
