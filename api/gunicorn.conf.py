"""
Gunicorn configuration for ITBP RTC Grain Shop API (production)
"""
import multiprocessing
import os

# ---------------------------------------------------------------------------
# Server socket
# ---------------------------------------------------------------------------
bind = f"0.0.0.0:{os.getenv('API_PORT', '5001')}"

# ---------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------
# A common formula: (2 * CPU cores) + 1
# Cap at 9 to stay sane inside a container with limited CPUs.
workers = min((2 * multiprocessing.cpu_count()) + 1, 9)
worker_class = "sync"           # sync is stable; switch to "gthread" if you need threading
threads = 1                     # threads per worker (only relevant for non-sync workers)
worker_connections = 1000       # max simultaneous clients (for async workers)

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = 120          # Kill workers that take longer than 2 min to respond
keepalive = 5          # Keep connections alive for 5 s between requests
graceful_timeout = 30  # Give workers 30 s to finish in-flight requests on shutdown

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
accesslog = "-"         # Stream access log to stdout (Docker-friendly)
errorlog = "-"          # Stream error log to stdout
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ---------------------------------------------------------------------------
# Process naming (visible in ps / top)
# ---------------------------------------------------------------------------
proc_name = "marutam_api"

# ---------------------------------------------------------------------------
# Security & performance
# ---------------------------------------------------------------------------
limit_request_line = 4096       # Max size of HTTP request line
limit_request_fields = 100      # Max number of headers
limit_request_field_size = 8190 # Max header field value size
forwarded_allow_ips = "*"       # Trust X-Forwarded-* headers from any proxy
