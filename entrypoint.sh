#!/bin/sh
set -e

# CPU-scaled workers: 2 * nproc + 1 (standard Gunicorn formula), capped at 9.
CPU_COUNT=$(nproc 2>/dev/null || echo 1)
COMPUTED_WORKERS=$((CPU_COUNT * 2 + 1))
if [ "$COMPUTED_WORKERS" -gt 9 ]; then COMPUTED_WORKERS=9; fi
WORKERS=${WEB_CONCURRENCY:-$COMPUTED_WORKERS}

python manage.py collectstatic --noinput --clear

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
    python manage.py migrate --noinput
fi

# Automatically create default admin user if it doesn't exist
python create_admin.py

exec gunicorn Rasayam_website.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "$WORKERS" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
