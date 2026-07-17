#!/bin/sh
# Backend entrypoint: wait for Postgres, migrate once, then exec the command.
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}…"
python - <<'PY'
import os, socket, sys, time

host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("PostgreSQL never became reachable", file=sys.stderr)
sys.exit(1)
PY

# Only the web process runs migrations/static collection — workers must not
# race it. RUN_MIGRATIONS defaults to true for the backend service.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Applying database migrations…"
  python manage.py migrate --noinput
  echo "Collecting static files…"
  python manage.py collectstatic --noinput
fi

exec "$@"
