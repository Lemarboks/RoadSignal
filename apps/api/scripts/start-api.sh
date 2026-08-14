#!/bin/sh
set -eu

load_secret() {
  variable=$1
  file_variable="${variable}_FILE"
  eval "secret_file=\${$file_variable:-}"
  if [ -n "$secret_file" ]; then
    if [ ! -r "$secret_file" ]; then
      echo "Secret file for $variable is not readable" >&2
      exit 1
    fi
    value=$(cat "$secret_file")
    export "$variable=$value"
  fi
}

load_secret DATABASE_URL
load_secret REDIS_URL
load_secret JWT_SECRET
load_secret METRICS_BEARER_TOKEN

if [ "${STORAGE_BACKEND:-memory}" = "mysql" ]; then
  python -m alembic -c alembic.ini upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="${TRUSTED_PROXY_IPS:-127.0.0.1}"