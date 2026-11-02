#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ "$EUID" -ne 0 ]]; then
  printf 'Run this script with sudo to access Docker.\n' >&2
  exit 1
fi

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
container="demo-toon-live"
backup_owner="kidd"
backup_group="$(id -gn "$backup_owner")"
backup_dir="/home/kidd/cloudops-lab/container-backups"

export_dir="$(mktemp -d)"
container_export="/tmp/demo-toon-export-$(basename "$export_dir").sqlite3"

cleanup() {
  docker exec "$container" rm -f -- "$container_export" \
    >/dev/null 2>&1 || true
  rm -f -- "$export_dir/snapshots.sqlite3"
  rmdir -- "$export_dir"
}
trap cleanup EXIT

# Export using the application's container user.
docker exec -i "$container" python - "$container_export" <<'PY'
import os
import sqlite3
import sys
from contextlib import closing

os.umask(0o077)

with closing(sqlite3.connect(
    "file:/data/snapshots.sqlite3?mode=ro", uri=True, timeout=5
)) as source:
    with closing(sqlite3.connect(sys.argv[1])) as destination:
        source.backup(destination)
        mode = destination.execute(
            "PRAGMA journal_mode=DELETE"
        ).fetchone()[0]
        result = destination.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if mode != "delete" or result != "ok":
            raise RuntimeError("Container export validation failed")

print("Container database export validated.")
PY

docker cp \
  "$container:$container_export" \
  "$export_dir/snapshots.sqlite3"

# Allow kidd to read the staging directory and exported database.
chown "$backup_owner:$backup_group" \
  "$export_dir" "$export_dir/snapshots.sqlite3"

# Reuse the existing backup validation and five-copy retention.
runuser -u "$backup_owner" -- env \
  SOURCE_DB="$export_dir/snapshots.sqlite3" \
  BACKUP_DIR="$backup_dir" \
  /usr/bin/bash "$project_dir/scripts/backup.sh"
