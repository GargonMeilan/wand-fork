#!/bin/sh
# Run from the checkout before Compose evaluates build contexts and bind mounts.
set -eu
cd "$(dirname "$0")/.."
git submodule sync --recursive
git submodule update --init --recursive
for file in houdini/Dockerfile houdini/houdini.sql dash/Dockerfile snowflake/Dockerfile legacy-media/media/boots.swf vanilla-media/play/index.html; do
    if [ ! -s "$file" ]; then
        echo "Missing submodule asset: $file. Deployment stopped before touching containers." >&2
        exit 1
    fi
done
