#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-compose.production.yml}
backup_dir=${BACKUP_DIR:-backups/mysql}
retention_days=${BACKUP_RETENTION_DAYS:-14}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
backup="$backup_dir/roadsignal-$timestamp.sql.enc"
key_file=${BACKUP_ENCRYPTION_KEY_FILE:-.secrets/backup_encryption_key}

if [ ! -s "$key_file" ]; then
  echo "Backup encryption key is missing: $key_file" >&2
  exit 1
fi

umask 077
mkdir -p "$backup_dir"
docker compose -f "$compose_file" exec -T db sh -c 'MYSQL_PWD=$(cat /run/secrets/mysql_password) exec mysqldump -u roadsignal --single-transaction --routines --triggers --events --no-tablespaces roadsignal' | openssl enc -aes-256-cbc -salt -pbkdf2 -pass "file:$key_file" -out "$backup"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$key_file" -in "$backup" | grep -q '^-- MySQL dump'
sha256sum "$backup" > "$backup.sha256"
find "$backup_dir" -type f -name 'roadsignal-*.sql*' -mtime "+$retention_days" -delete
echo "Verified encrypted backup written to $backup"
