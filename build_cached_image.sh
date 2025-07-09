# Version: "v0.0.1" must be replaced manually in this script and in Dockerfile
# Then this script needs to be run manually
# Then push git commit to GitHub and tag it so finall image is built and pushed to Docker hub

echo "This script is currently WIP and are just notes with commands."
exit 0

# -------- JUST FOR ONE PLATFORM ------

# Change version manually as this will be run very rarely
docker build -f Dockerfile.cache -t pdfix/pdf-accessibility-paddle-cache:v0.0.1 .
docker build --platform linux/amd64 -f Dockerfile.cache -t pdfix/pdf-accessibility-paddle-cache:v0.0.1 .


# Push to Docker Hub
# For this step you need to be logged in to Docker Hub
# You can log in using `docker login`
docker push pdfix/pdf-accessibility-paddle-cache:v0.0.1

# -------- 2 OR MORE PLATFORMS ------

# check for
# Driver: docker-container
# Platforms: linux/amd64, linux/arm64, ...

# create builder:
docker buildx create --use --name multiarch-builder --driver docker-container
docker buildx inspect --bootstrap

# build and push
docker buildx build --platform linux/amd64,linux/arm64 -f Dockerfile.cache -t pdfix/pdf-accessibility-paddle-cache:v0.0.2 --push .
