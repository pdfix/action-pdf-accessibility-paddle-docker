#!/bin/bash

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
sed -i "s/latest/$1/g" config.json

echo "Replaced all occurrences of 'latest' with '$1' in config.json."
