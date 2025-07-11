#!/bin/bash
# Run this script using "./build_cached_image.sh v0.0.1"

set -euo pipefail

# === 0. INPUT ARGUMENT ===
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <VERSION>"
    exit 1
fi

# === 1. CONFIGURATION ===
BUILDER_NAME="multiarch-builder"
# This needs to be updated manually (as it runs only once a while it is ok to keep it as manual process)
VERSION_NAME=$1
IMAGE_NAME="pdfix/pdf-accessibility-paddle-cache:$VERSION_NAME"
DOCKERFILE="Dockerfile.cache"
PLATFORMS="linux/amd64,linux/arm64"

# === 2. CHECK DOCKER LOGIN STATUS ===
echo "🔐 Checking if user is logged in to Docker Hub..."

if grep -q '"auths"' ~/.docker/config.json && grep -q 'https://index.docker.io/v1/' ~/.docker/config.json; then
  echo "✅ Docker login found in config.json"
else
  echo "❌ Not logged in to Docker Hub. Please run: docker login"
  exit 1
fi

# === 3. REMOVE EXISTING BUILDX BUILDER IF EXISTS ===
echo "🧹 Cleaning up existing buildx builder and containers..."

if docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    echo "🔍 Found existing builder: $BUILDER_NAME — removing..."
    docker buildx rm "$BUILDER_NAME"
fi

# === 4. REMOVE ANY LEFTOVER BUILDX CONTAINERS ===
echo "🧼 Removing dangling buildx containers (if any)..."

docker ps -a --filter "name=buildx_buildkit_" --format "{{.ID}}" | xargs -r docker rm -f

# === 5. CREATE NEW BUILDX BUILDER ===
echo "🚧 Creating new buildx builder: $BUILDER_NAME"

docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
docker buildx inspect --bootstrap

# === 6. BUILD AND PUSH MULTI-ARCH IMAGE ===
echo "🐳 Building and pushing image: $IMAGE_NAME"

docker buildx build \
  --platform "$PLATFORMS" \
  -f "$DOCKERFILE" \
  -t "$IMAGE_NAME" \
  --push \
  .

# === 7. CLEANUP BUILDER + CONTAINERS ===
echo "🧹 Cleaning up builder and containers..."

docker buildx rm "$BUILDER_NAME"

# === 8. REMOVE LEFTOVER BUILDX CONTAINERS AGAIN JUST IN CASE ===
docker ps -a --filter "name=buildx_buildkit_" --format "{{.ID}}" | xargs -r docker rm -f

echo "✅ Done!"
