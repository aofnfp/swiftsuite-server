#!/usr/bin/env sh
set -e

case "$1" in
    web)
        echo "Running database migrations..."
        python manage.py migrate --noinput

        # python manage.py tier_seeds

        echo "Starting Gunicorn..."
        exec gunicorn --bind 0.0.0.0:8000 swiftsuite.wsgi:application --workers 4
    ;;
    celery)
        echo "Starting Celery worker..."
        exec celery -A swiftsuite worker -l info -c 4 --pool=threads
    ;;
    beat)
        echo "Starting Beat worker..."
        celery -A swiftsuite beat -l info
    ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: entrypoint.sh {web|celery|celery-beat}"
        exit 1
    ;;
esac