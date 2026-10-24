#!/bin/bash
cd /srv/rasayam
source venv/bin/activate
set -a
source .env
set +a
exec gunicorn Rasayam_website.wsgi:application --workers 2 --bind 127.0.0.1:8000
