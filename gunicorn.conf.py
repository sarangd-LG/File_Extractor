import os

bind = "0.0.0.0:9797"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "sync"
threads = 1
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
capture_output = True
