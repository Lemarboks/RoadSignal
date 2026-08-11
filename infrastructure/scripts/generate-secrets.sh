#!/bin/sh
set -eu

secret_dir=${SECRETS_DIR:-.secrets}
if [ -e "$secret_dir" ] && [ "$(find "$secret_dir" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]; then
  echo "Refusing to overwrite existing secrets in $secret_dir" >&2
  exit 1
fi

umask 077
mkdir -p "$secret_dir"
postgres_password=$(openssl rand -hex 32)
redis_password=$(openssl rand -hex 32)

printf '%s' "$postgres_password" > "$secret_dir/postgres_password"
printf 'postgresql+psycopg://saferoute:%s@db:5432/saferoute' "$postgres_password" > "$secret_dir/database_url"
printf '%s' "$redis_password" > "$secret_dir/redis_password"
printf 'redis://:%s@redis:6379/0' "$redis_password" > "$secret_dir/redis_url"
openssl rand -hex 48 | tr -d '\n' > "$secret_dir/jwt_secret"
openssl rand -hex 32 | tr -d '\n' > "$secret_dir/metrics_token"
chmod 0444 "$secret_dir"/*

echo "Created six restricted secret files in $secret_dir"
