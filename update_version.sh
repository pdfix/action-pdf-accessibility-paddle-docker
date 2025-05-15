#!/bin/bash

# This script is used to update the version number in the config.json file
# during the Docker build process in GitHub Actions.
# It replace latest in program arguments with current version of container.
# It also replaces the version number in the config.json file.

# Check if an argument is provided
if [ -z "$1" ]; then
    echo "No argument provided. Usage: ./update_version.sh <argument>"
    exit 1
fi

# Check if the input is "latest"
if [ "$1" == "latest" ]; then
    echo "Input is 'latest'. No changes made."
    exit 0
fi

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "File config.json does not exist."
    exit 1
fi

# Replace "latest" with the provided argument in config.json
# usually program argument
sed -i "s/latest/$1/g" config.json

echo "Replaced all occurrences of 'latest' with '$1' in config.json."

# Replace "v0.0.0" with the provided argument in config.json
# usually "version" : "v0.0.0"
sed -i "s/v0\.0\.0/v$1/g" config.json

echo "Replaced all occurrences of 'v0.0.0' with 'v$1' in config.json."
