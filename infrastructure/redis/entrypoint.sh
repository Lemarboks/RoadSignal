#!/bin/sh
set -eu

if [ ! -r /run/secrets/redis_password ]; then
  echo "Redis password secret is not readable" >&2
  exit 1
fi
printf 'appendonly yes\nprotected-mode yes\nrequirepass %s\n' "$(cat /run/secrets/redis_password)" > /tmp/redis.conf
exec docker-entrypoint.sh "$@"
