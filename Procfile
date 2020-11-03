web: gunicorn app:app
worker: celery worker -A eilxc.celery --loglevel=info --concurrency=1
