#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres to accept connections (compose/Render race-safe).
echo "[entrypoint] waiting for database..."
python - <<'PY'
import os, time, psycopg
url = os.environ["DATABASE_URL"]
for i in range(60):
    try:
        with psycopg.connect(url, connect_timeout=3) as c:
            c.execute("SELECT 1")
        print("[entrypoint] database is ready")
        break
    except Exception as e:
        print(f"  ...not ready ({e}); retrying")
        time.sleep(2)
else:
    raise SystemExit("database never became ready")
PY

# Ingest only when empty (idempotent across restarts) unless FORCE_INGEST=1.
if [ "${FORCE_INGEST:-0}" = "1" ]; then
  echo "[entrypoint] FORCE_INGEST=1 -> re-ingesting"
  python -m app.ingest.run_all
else
  NEEDS_INGEST=$(python - <<'PY'
import os, psycopg
try:
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as c:
        n = c.execute("SELECT count(*) FROM documents").fetchone()[0]
    print("0" if n > 0 else "1")
except Exception:
    print("1")
PY
)
  if [ "$NEEDS_INGEST" = "1" ]; then
    echo "[entrypoint] empty store -> ingesting"
    python -m app.ingest.run_all
  else
    echo "[entrypoint] data already present -> skipping ingest"
  fi
fi

echo "[entrypoint] starting API on :${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
