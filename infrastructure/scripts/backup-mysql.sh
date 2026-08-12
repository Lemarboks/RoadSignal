#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-compose.production.yml}
backup_dir=${BACKUP_DIR:-backups/mysql}
retention_days=${BACKUP_RETENTION_DAYS:-14}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
backup="$backup_dir/saferoute-$timestamp.sql"

umask 077
mkdir -p "$backup_dir"
docker compose -f "$compose_file" exec -T db sh -c 'MYSQL_PWD=$(cat /run/secrets/mysql_password) exec mysqldump -u saferoute --single-transaction --routines --triggers --events --no-tablespaces saferoute' > "$backup"
grep -q '^-- MySQL dump' "$backup"
grep -q '^CREATE TABLE' "$backup"
sha256sum "$backup" > "$backup.sha256"
find "$backup_dir" -type f -name 'saferoute-*.sql*' -mtime "+$retention_days" -delete
echo "Verified backup written to $backup"
