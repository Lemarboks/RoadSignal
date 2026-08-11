#!/bin/sh
set -eu
python -m alembic -c alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="${TRUSTED_PROXY_IPS:-127.0.0.1}"
