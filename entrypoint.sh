#!/usr/bin/env sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

python manage.py tier_seeds

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 swiftsuite.wsgi:application --workers 4
