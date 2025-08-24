#!/usr/bin/env sh
set -e

echo "Running database migrations..."
python app/manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 swiftsuite.wsgi:application --workers 4
