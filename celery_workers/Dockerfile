FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Command to run Celery worker
# --concurrency: Number of concurrent processes/threads. Adjust based on CPU/RAM.
# -P eventlet: Use Eventlet pool for better I/O concurrency (requires eventlet in requirements.txt)
# If eventlet causes issues, remove `-P eventlet` and rely on default `fork` pool or `-P solo`.
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=200", "-P", "eventlet"]
