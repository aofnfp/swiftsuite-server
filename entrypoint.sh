#!/usr/bin/env sh
set -e

case "$1" in
    web)
        echo "Running database migrations..."
        python manage.py migrate --noinput

        echo "Starting Gunicorn..."
        exec gunicorn swiftsuite.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers 4 \
            --threads 2 \
            --timeout 120
    ;;

    celery-default)
        echo "Starting Celery default worker (short tasks)..."
        exec celery -A swiftsuite worker -l info -Q default -c 500 --pool=gevent
    ;;

    celery-heavy)
        echo "Starting Celery heavy worker (long tasks)..."
        exec celery -A swiftsuite worker \
            --loglevel=info \
            --queues=heavy \
            --concurrency=2 \
            --pool=prefork \
            --time-limit=1800 \
            --soft-time-limit=1700
    ;;

    beat)
        echo "Starting Celery Beat..."
        exec celery -A swiftsuite beat --loglevel=info

    ;;

    *)
        echo "Unknown command: $1"
        echo "Usage: entrypoint.sh {web|celery-default|celery-heavy|beat}"
        exit 1
    ;;
esac





# #!/usr/bin/env sh
# set -e

# case "$1" in
#     web)
#         echo "Running database migrations..."
#         python manage.py migrate --noinput

#         # python manage.py seed_module
#         # python manage.py seed_charge

#         echo "Starting Gunicorn..."
#         exec gunicorn --bind 0.0.0.0:8000 swiftsuite.wsgi:application --workers 4
#     ;;
#     celery-default)
#         echo "Starting Celery default worker (light tasks)..."
#         exec celery -A swiftsuite worker -l info -Q default -c 8 --pool=prefork
#     ;;

#     celery-heavy)
#         echo "Starting Celery heavy worker (long tasks)..."
#         exec celery -A swiftsuite worker -l info -Q heavy -c 2 --pool=prefork
#     ;;

#     beat)
#         echo "Starting Beat worker..."
#         exec celery -A swiftsuite beat -l info
#     ;;

#     *)
#         echo "Unknown command: $1"
#         echo "Usage: entrypoint.sh {web|celery-default|celery-heavy|celery-beat}"
#         exit 1
#     ;;
# esac

