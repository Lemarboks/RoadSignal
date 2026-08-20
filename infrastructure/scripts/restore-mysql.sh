#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: CONFIRM_RESTORE=roadsignal $0 <backup.sql>" >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-}" != "roadsignal" ]; then
  echo "Restore is destructive. Re-run with CONFIRM_RESTORE=roadsignal." >&2
  exit 2
fi

backup=$1
key_file=${BACKUP_ENCRYPTION_KEY_FILE:-.secrets/backup_encryption_key}
compose_file=${COMPOSE_FILE:-compose.production.yml}
if [ ! -f "$backup" ] || [ ! -f "$backup.sha256" ]; then
  echo "Backup or checksum file is missing: $backup" >&2
  exit 1
fi

sha256sum -c "$backup.sha256"
if [ ! -s "$key_file" ]; then
  echo "Backup encryption key is missing: $key_file" >&2
  exit 1
fi
openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$key_file" -in "$backup" | grep -q '^-- MySQL dump'
safety_dir=${BACKUP_DIR:-backups/mysql}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKUP_DIR="$safety_dir" "$script_dir/backup-mysql.sh"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$key_file" -in "$backup" | docker compose -f "$compose_file" exec -T db sh -c 'MYSQL_PWD=$(cat /run/secrets/mysql_password) exec mysql -u roadsignal roadsignal'
echo "Restore completed from $backup"
