#!/usr/bin/env sh
set -e

# Seed sample uploads if target folder is empty
if [ -d "/app/uploads" ]; then
  if [ -z "$(ls -A /app/uploads 2>/dev/null)" ]; then
    if [ -d "/app/uploads-sample" ]; then
      cp -a /app/uploads-sample/. /app/uploads/
    fi
  fi
else
  mkdir -p /app/uploads
  if [ -d "/app/uploads-sample" ]; then
    cp -a /app/uploads-sample/. /app/uploads/
  fi
fi

exec "$@"
