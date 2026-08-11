#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-compose.production.yml}
backup_dir=${BACKUP_DIR:-backups/postgres}
retention_days=${BACKUP_RETENTION_DAYS:-14}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
backup="$backup_dir/saferoute-$timestamp.dump"

umask 077
mkdir -p "$backup_dir"
docker compose -f "$compose_file" exec -T db pg_dump -U saferoute -d saferoute --format=custom --no-owner --no-acl > "$backup"
docker compose -f "$compose_file" exec -T db pg_restore --list < "$backup" >/dev/null
sha256sum "$backup" > "$backup.sha256"
find "$backup_dir" -type f -name 'saferoute-*.dump*' -mtime "+$retention_days" -delete
echo "Verified backup written to $backup"
