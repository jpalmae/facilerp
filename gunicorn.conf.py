from __future__ import annotations

import multiprocessing
import os


bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
worker_tmp_dir = "/dev/shm"
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# --- Performance & reliability tuning ---
# Restart workers periodically to prevent memory leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))

# Preload app to share memory across workers
preload_app = os.getenv("GUNICORN_PRELOAD_APP", "true").lower() == "true"

# Worker connection limit
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))

# Max request body size (50MB)
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "8190"))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "8190"))

# Graceful worker timeout handling
max_worker_age = int(os.getenv("GUNICORN_MAX_WORKER_AGE", "600"))  # 10 min
