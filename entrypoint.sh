#!/usr/bin/env sh
# set -e

# case "$1" in
#     web)
#         echo "Running database migrations..."
#         python manage.py migrate --noinput

#         echo "Starting Gunicorn..."
#         exec gunicorn swiftsuite.wsgi:application \
#             --bind 0.0.0.0:8000 \
#             --workers=4 \
#             --threads=2 \
#             --timeout=120
#     ;;

#     celery-default)
#         echo "Starting Celery default worker (short I/O tasks)..."
#         exec celery -A swiftsuite worker \
#             --queues=default \
#             --loglevel=info \
#             --pool=gevent \
#             --concurrency=50 \
            
#     ;;

#     celery-heavy-io)
#         echo "Starting Celery heavy I/O worker (large vendor syncs)..."
#         exec celery -A swiftsuite worker \
#             --queues=heavy-io \
#             --loglevel=info \
#             --pool=gevent \
#             --concurrency=8 \
#             --heartbeat-interval=30 \
#             --soft-time-limit=300 \
#             --time-limit=360
#     ;;

#     celery-heavy-cpu)
#         echo "Starting Celery heavy CPU worker (compute tasks)..."
#         exec celery -A swiftsuite worker \
#             --queues=heavy-cpu \
#             --loglevel=info \
#             --pool=prefork \
#             --concurrency=2 \
#             --heartbeat-interval=30 \
#             --soft-time-limit=300 \
#             --time-limit=360
#     ;;

#     celery-heavy-inv)
#         echo "Starting Celery inventory worker (stable mode to avoid heartbeats)..."
#         exec celery -A swiftsuite worker \
#             --queues=heavy-inv \
#             --loglevel=info \
#             --pool=solo \
#             --concurrency=1 \
#             --heartbeat-interval=30 \
#             --time-limit=360
#     ;;

#     beat)
#         echo "Starting Celery Beat..."
#         exec celery -A swiftsuite beat --loglevel=info
#     ;;

#     *)
#         echo "Unknown command: $1"
#         echo "Usage: entrypoint.sh {web|celery-default|celery-heavy-io|celery-heavy-cpu|celery-heavy-inv|beat}"
#         exit 1
#     ;;
# esac




# #!/usr/bin/env sh
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
    ;;

    celery-default)
        echo "Starting Celery default worker (short I/O tasks)..."
        exec celery -A swiftsuite worker \
            --loglevel=info \
            --queues=default \
            --concurrency=10 \
            --pool=gevent
    ;;

    celery-heavy-io)
        echo "Starting Celery heavy I/O worker (large vendor syncs)..."
        exec celery -A swiftsuite worker \
            --loglevel=info \
            --queues=heavy-io \
            --concurrency=10 \
            --pool=gevent
    ;;

    celery-heavy-cpu)
        echo "Starting Celery heavy CPU worker (compute-intensive tasks)..."
        exec celery -A swiftsuite worker \
            --loglevel=info \
            --queues=heavy-cpu \
            --concurrency=3 \
            --pool=prefork
    ;;

    celery-heavy-inv)
        echo "Starting Celery heavy CPU worker (compute-intensive tasks)..."
        exec celery -A swiftsuite worker \
            --queues=heavy-inv \
            --loglevel=info \
            --pool=solo \
            --concurrency=3 \
    ;;


    beat)
        echo "Starting Celery Beat..."
        exec celery -A swiftsuite beat --loglevel=info
    ;;

    *)
        echo "Unknown command: $1"
        echo "Usage: entrypoint.sh {web|celery-default|celery-heavy-io|celery-heavy-cpu|beat}"
        exit 1
    ;;
esac
