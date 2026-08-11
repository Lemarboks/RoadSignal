#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: CONFIRM_RESTORE=saferoute $0 <backup.dump>" >&2
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
docker compose -f "$compose_file" exec -T db pg_restore --list < "$backup" >/dev/null
safety_dir=${BACKUP_DIR:-backups/postgres}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKUP_DIR="$safety_dir" "$script_dir/backup-postgres.sh"
docker compose -f "$compose_file" exec -T db pg_restore -U saferoute -d saferoute --clean --if-exists --no-owner --no-acl < "$backup"
echo "Restore completed from $backup"
