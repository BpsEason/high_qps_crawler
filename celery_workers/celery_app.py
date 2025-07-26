from celery import Celery

# Redis as broker and backend
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'

app = Celery('crawler_tasks',
             broker=CELERY_BROKER_URL,
             backend=CELERY_RESULT_BACKEND,
             include=['app.tasks']) # Include tasks from app/tasks.py

app.conf.update(
    task_track_started=True,
    task_acks_late=True, # Acknowledge tasks after completion
    worker_prefetch_multiplier=4, # Increase prefetch for better throughput (adjust based on task nature)
    broker_connection_retry_on_startup=True,
    task_serializer='json', # Use JSON serializer for tasks
    result_serializer='json', # Use JSON serializer for results
    accept_content=['json'], # Accept JSON content
    task_annotations = {'*': {'rate_limit': '3000/m'}} # Example: Global rate limit 3000 tasks/minute
)

if __name__ == '__main__':
    app.start()
