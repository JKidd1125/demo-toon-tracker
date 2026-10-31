#!/usr/bin/env bash
set -euo pipefail
umask 077

# Locate the project independently of the current working directory.
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_db="${SOURCE_DB:-$project_dir/data/snapshots.sqlite3}"
backup_dir="${BACKUP_DIR:-$HOME/cloudops-lab/backups}"

# Refuse to create a backup from a missing source.
if [[ ! -f "$source_db" ]]; then
  printf 'Source database not found: %s\n' "$source_db" >&2
  exit 1
fi

mkdir -p -- "$backup_dir"

# Create a unique temporary destination.
temporary_backup="$(mktemp "$backup_dir/demo-toon-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.partial")"

# Clean up this operation's temporary files when the script exits.
trap 'rm -f -- "$temporary_backup" "${temporary_backup}-wal" "${temporary_backup}-shm" "${temporary_backup}-journal"' EXIT

# Take a consistent backup while the application keeps running.
sqlite3 -readonly "$source_db" \
  ".timeout 5000" \
  ".backup '$temporary_backup'"

# Finalize the backup as a standalone file.
# DELETE changes the journal mode; it does not delete records.
backup_journal_mode="$(sqlite3 "$temporary_backup" \
  ".timeout 5000" \
  "PRAGMA journal_mode=DELETE;")"

if [[ "$backup_journal_mode" != "delete" ]]; then
  printf 'Could not finalize backup journal mode.\n' >&2
  exit 1
fi

# Validate before publishing the backup or deleting older backups.
integrity_result="$(sqlite3 -readonly "$temporary_backup" \
  'PRAGMA integrity_check;')"

if [[ "$integrity_result" != "ok" ]]; then
  printf 'Backup integrity check failed: %s\n' "$integrity_result" >&2
  exit 1
fi

# Rename the validated backup to its completed filename.
backup_file="${temporary_backup%.partial}.sqlite3"
mv -- "$temporary_backup" "$backup_file"

printf 'Verified backup created: %s\n' "$backup_file"
sha256sum "$backup_file"

# Retain the five newest matching completed backups.
# PRUNE_DRY_RUN=1 previews deletion without removing old backups.
python3 - "$backup_dir" <<'PY'
import os
import re
import sys
from pathlib import Path

backup_dir = Path(sys.argv[1])
pattern = re.compile(
    r"demo-toon-\d{8}T\d{6}Z(?:-[A-Za-z0-9]{6})?\.sqlite3"
)
dry_run = os.environ.get("PRUNE_DRY_RUN") == "1"

backups = [
    path for path in backup_dir.iterdir()
    if pattern.fullmatch(path.name)
    and not path.is_symlink()
    and path.is_file()
]
backups.sort(
    key=lambda path: (path.stat().st_mtime_ns, path.name),
    reverse=True,
)

for path in backups[5:]:
    if dry_run:
        print(f"Would remove old backup: {path}")
    else:
        path.unlink()
        print(f"Removed old backup: {path}")

retained = min(len(backups), 5)
if dry_run:
    print(f"Retention preview: found {len(backups)}, would keep {retained}.")
else:
    print(f"Retention complete: found {len(backups)}, kept {retained}.")
PY
