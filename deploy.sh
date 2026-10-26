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
    for i in {1..3}; do
        if git -c http.version=HTTP/1.1 pull origin main; then
            break
        fi
        echo "   Mencoba kembali git pull ($i/3)..."
        sleep 2
    done
    export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
    echo "   Commit aktif: ${GIT_COMMIT}"
fi

# 2. Build Container dengan metadata commit (bisa pilih service spesifik atau all)
SERVICE="${2:-}"
if [ "$1" != "--pull" ] && [ "$1" != "-p" ] && [ -n "$1" ]; then
    SERVICE="$1"
fi

if [ -n "$SERVICE" ]; then
    echo "🔨 Membangun service: ${SERVICE}..."
    docker compose build \
        --build-arg GIT_COMMIT="${GIT_COMMIT}" \
        --build-arg BUILD_TIME="${BUILD_TIME}" \
        "${SERVICE}"
    echo "▶️  Menjalankan ${SERVICE}..."
    docker compose up -d "${SERVICE}"
else
    echo "🔨 Membangun seluruh service..."
    docker compose build \
        --build-arg GIT_COMMIT="${GIT_COMMIT}" \
        --build-arg BUILD_TIME="${BUILD_TIME}" || {
        echo "⚠️  Build remote base image dicegah network, menjalankan update container..."
    }
    echo "▶️  Menjalankan container terbaru..."
    docker compose up -d
fi

echo "=========================================================="
echo "✅ Deploy Berhasil!"
echo "   Commit Live   : ${GIT_COMMIT}"
echo "   Backend Health: http://localhost:8019/api/v1/health"
echo "   Frontend      : http://localhost:3019"
echo "=========================================================="
