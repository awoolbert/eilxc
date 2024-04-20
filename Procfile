web: gunicorn app:app
worker: celery worker -A hsxc.celery --loglevel=info --concurrency=1
