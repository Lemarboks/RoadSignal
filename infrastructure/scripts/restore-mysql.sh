#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: CONFIRM_RESTORE=saferoute $0 <backup.sql>" >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-}" != "saferoute" ]; then
  echo "Restore is destructive. Re-run with CONFIRM_RESTORE=saferoute." >&2
  exit 2
fi

backup=$1
compose_file=${COMPOSE_FILE:-compose.production.yml}
if [ ! -f "$backup" ] || [ ! -f "$backup.sha256" ]; then
  echo "Backup or checksum file is missing: $backup" >&2
  exit 1
fi

sha256sum -c "$backup.sha256"
grep -q '^-- MySQL dump' "$backup"
grep -q '^CREATE TABLE' "$backup"
safety_dir=${BACKUP_DIR:-backups/mysql}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKUP_DIR="$safety_dir" "$script_dir/backup-mysql.sh"
docker compose -f "$compose_file" exec -T db sh -c 'MYSQL_PWD=$(cat /run/secrets/mysql_password) exec mysql -u saferoute saferoute' < "$backup"
echo "Restore completed from $backup"
