# Version: "v0.0.1" must be replaced manually in this script and in Dockerfile
# Then this script needs to be run manually
# Then push git commit to GitHub and tag it so finall image is built and pushed to Docker hub


# Change version manually as this will be run very rarely
docker build -f Dockerfile.cache -t pdfix/pdf-accessibility-paddle-cache:v0.0.1 .


# Push to Docker Hub
# For this step you need to be logged in to Docker Hub
# You can log in using `docker login`
docker push pdfix/pdf-accessibility-paddle-cache:v0.0.1
