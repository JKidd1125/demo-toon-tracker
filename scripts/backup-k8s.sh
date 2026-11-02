#!/usr/bin/env bash
set -euo pipefail
umask 077

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
namespace="demo-toon"
backup_dir="$HOME/cloudops-lab/k8s-backups"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

# Allow the application time to become ready after cluster startup.
kubectl rollout status deployment/demo-toon-tracker \
  --namespace "$namespace" \
  --timeout=90s

# Find the running tracker pod rather than hard-coding its changing name.
pod="$(kubectl get pods \
  --namespace "$namespace" \
  --selector app=demo-toon-tracker \
  --field-selector status.phase=Running \
  --output jsonpath='{.items[0].metadata.name}')"

if [[ -z "$pod" ]]; then
  printf 'No running tracker pod found.\n' >&2
  exit 1
fi

export_dir="$(mktemp -d)"
pod_export="/tmp/demo-toon-export-$(basename "$export_dir").sqlite3"

cleanup() {
  kubectl exec --namespace "$namespace" "$pod" -- \
    rm -f -- "$pod_export" >/dev/null 2>&1 || true
  rm -f -- "$export_dir/snapshots.sqlite3"
  rmdir -- "$export_dir"
}
trap cleanup EXIT

# Create a consistent, validated export inside the selected pod.
kubectl exec --namespace "$namespace" -i "$pod" -- \
  python - "$pod_export" <<'PY'
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
            raise RuntimeError("Kubernetes export validation failed")

        count, latest_id = destination.execute(
            "SELECT COUNT(*), MAX(id) FROM snapshots WHERE is_demo = 0"
        ).fetchone()

print(
    f"Kubernetes export validated; live snapshots: {count}; "
    f"latest live ID: {latest_id}"
)
PY

# Stream the completed export into the private host staging directory.
kubectl exec --namespace "$namespace" "$pod" -- \
  python -c '
import shutil
import sys

with open(sys.argv[1], "rb") as source:
    shutil.copyfileobj(source, sys.stdout.buffer)
' "$pod_export" > "$export_dir/snapshots.sqlite3"

# Reuse the existing validation and five-copy retention procedure.
SOURCE_DB="$export_dir/snapshots.sqlite3" \
BACKUP_DIR="$backup_dir" \
  /usr/bin/bash "$project_dir/scripts/backup.sh"
