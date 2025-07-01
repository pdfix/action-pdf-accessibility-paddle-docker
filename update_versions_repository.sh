#!/bin/bash

# This script is used to update versions respository (if )
# This way history is preserved and we can track changes

set -e

# Expecting 3 arguments:
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <DOCKER_HUB_NAMESPACE> <DOCKER_HUB_REPOSITORY> <TAG>"
    exit 1
fi

DOCKER_HUB_NAMESPACE=$1
DOCKER_HUB_REPOSITORY=$2
TAG=$3

DOCKER_NAME="${DOCKER_HUB_NAMESPACE}/${DOCKER_HUB_REPOSITORY}"
VERSIONS_JSON="pdfix-version-updates/v1/versions.json"
TEMPORARY_FILE="tmp_versions.json"

# Step 1: Check if app is in version history
if jq -e --arg name "$DOCKER_NAME" '.["pdfix-actions"][] | select(.name == $name)' "$VERSIONS_JSON" > /dev/null; then
    echo "App found in version history."

    # Step 2: Update action version and date
    TODAY=$(date +%Y-%m-%d)
    jq --indent 4 --arg name "$DOCKER_NAME" --arg version "$TAG" --arg date "$TODAY" \
        '(.["pdfix-actions"][] | select(.name == $name)) |= . + {
            "version": $version,
            "release_date": $date
        }' $VERSIONS_JSON > $TEMPORARY_FILE
    mv $TEMPORARY_FILE $VERSIONS_JSON

    # Step 3: Commit and push changes
    cd pdfix-version-updates
    git config user.name "PDFix Support"
    git config user.email "support@pdfix.net"
    git add v1/versions.json
    git commit -m "$DOCKER_NAME $TAG"
    git push

    # Step 4: Tag latest commit with increment
    git pull
    if git describe --exact-match --tags HEAD > /dev/null 2>&1; then
        echo "HEAD already has a tag — skipping tagging."
    else
        LATEST_TAG=$(git tag -l "v*.*.*" | sort -V | tail -n 1)
        echo "Latest tag is: $LATEST_TAG"
        VERSION=${LATEST_TAG#v}
        IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"
        PATCH=$((PATCH + 1))
        NEW_TAG="v$MAJOR.$MINOR.$PATCH"
        git tag -a "$NEW_TAG" -m "Release $NEW_TAG"
        git push origin "$NEW_TAG"
        echo "Tagged HEAD with: $NEW_TAG"
    fi

else
    echo "App not found in version history. Skipping update steps."
fi
