#!/bin/bash

# This is local docker test during build and push action.

# Colors for output into console
GREEN='\033[0;32m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print info messages
info() { echo -e "${PURPLE}$1${NC}"; }

# Function to print success messages
success() { echo -e "${GREEN}$1${NC}"; }

# Function to print error messages
error() { echo -e "${RED}ERROR: $1${NC}"; }

# init
pushd "$(dirname $0)" > /dev/null

EXIT_STATUS=0
DOCKER_IMAGE="pdf-accessibility-paddle:test"
PLATFORM="--platform linux/amd64"
TEMPORARY_DIRECTORY=".test"

info "Building docker image..."
docker build -f Dockerfile $PLATFORM -t $DOCKER_IMAGE .

if [ -d "$(pwd)/$TEMPORARY_DIRECTORY" ]; then
    rm -rf $(pwd)/$TEMPORARY_DIRECTORY
fi
mkdir -p $(pwd)/$TEMPORARY_DIRECTORY

info "List files in /usr/paddlex"
docker run --rm $PLATFORM -v $(pwd):/data -w /data --entrypoint ls $DOCKER_IMAGE /usr/paddlex/

info "Test #01: Show help"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE --help > /dev/null
if [ $? -eq 0 ]; then
    success "passed"
else
    error "Failed to run \"--help\" command"
    EXIT_STATUS=1
fi

info "Test #02: Extract config"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE config -o $TEMPORARY_DIRECTORY/config.json > /dev/null
if [ -f "$(pwd)/$TEMPORARY_DIRECTORY/config.json" ]; then
    success "passed"
else
    error "config.json not saved"
    EXIT_STATUS=1
fi

info "Test #03: Run autotag"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE tag -i example/air_quality.pdf -o $TEMPORARY_DIRECTORY/air_quality-tagged.pdf > /dev/null
if [ -f "$(pwd)/$TEMPORARY_DIRECTORY/air_quality-tagged.pdf" ]; then
    success "passed"
else
    error "autotag failed on example/air_quality.pdf"
    EXIT_STATUS=1
fi

info "Test #04: Run create template"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE template -i example/air_quality.pdf -o $TEMPORARY_DIRECTORY/air_quality.json > /dev/null
if [ -f "$(pwd)/$TEMPORARY_DIRECTORY/air_quality.json" ]; then
    success "passed"
else
    error "create template failed on example/air_quality.pdf"
    EXIT_STATUS=1
fi

info "Test #05: Run mathml pdf->pdf"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE mathml -i $TEMPORARY_DIRECTORY/air_quality-tagged.pdf -o $TEMPORARY_DIRECTORY/air_quality-mathml.pdf > /dev/null
if [ -f "$(pwd)/$TEMPORARY_DIRECTORY/air_quality-mathml.pdf" ]; then
    success "passed"
else
    error "mathml pdf->pdf failed on $TEMPORARY_DIRECTORY/air_quality-tagged.pdf"
    EXIT_STATUS=1
fi

info "Test #06: Run mathml img->xml"
docker run --rm $PLATFORM -v $(pwd):/data -w /data $DOCKER_IMAGE mathml -i example/formula_example.jpg -o $TEMPORARY_DIRECTORY/formula_example.xml > /dev/null
if [ -f "$(pwd)/$TEMPORARY_DIRECTORY/formula_example.xml" ]; then
    success "passed"
else
    error "mathml img->xml failed on example/formula_example.jpg"
    EXIT_STATUS=1
fi

info "Cleaning up temporary files from tests"
rm -f $TEMPORARY_DIRECTORY/config.json
rm -f $TEMPORARY_DIRECTORY/air_quality-tagged.pdf
rm -f $TEMPORARY_DIRECTORY/air_quality.json
rm -f $TEMPORARY_DIRECTORY/air_quality-mathml.pdf
rm -f $TEMPORARY_DIRECTORY/formula_example.xml
rmdir $(pwd)/$TEMPORARY_DIRECTORY

info "Removing testing docker image"
docker rmi $DOCKER_IMAGE

popd > /dev/null

if [ $EXIT_STATUS -eq 1 ]; then
    error "One or more tests failed."
    exit 1
else
    success "All tests passed."
    exit 0
fi
