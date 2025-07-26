from celery_app import app
import asyncio
import motor.motor_asyncio as AsyncIOMotorClient # for MongoDB
from pymongo import InsertOne # For bulk operations
import asyncpg # for PostgreSQL
import datetime
import os # For environment variables
import redis.asyncio as aioredis # For updating task status in Redis

# Environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# --- IMPORTANT: CHOOSE YOUR DATABASE ---
# PostgreSQL Configuration (Default enabled for this script version)
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://user:password@postgresql:5432/crawler_db")

# MongoDB Configuration (Commented out by default)
# MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")

_mongo_client = None # Global MongoDB client for connection pooling
_pg_pool = None      # Global PostgreSQL connection pool

async def get_redis_client():
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")

async def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        if 'MONGODB_URL' in os.environ and os.environ['MONGODB_URL']:
            _mongo_client = AsyncIOMotorClient.AsyncIOMotorClient(os.environ['MONGODB_URL'])
        else:
            raise ValueError("MONGODB_URL is not set for MongoDB connection.")
    return _mongo_client

async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        if 'POSTGRES_URL' in os.environ and os.environ['POSTGRES_URL']:
            _pg_pool = await asyncpg.create_pool(os.environ['POSTGRES_URL'], min_size=10, max_size=50) # Adjust pool size
        else:
            raise ValueError("POSTGRES_URL is not set for PostgreSQL connection.")
    return _pg_pool

@app.task(name='tasks.store_data', bind=True, default_retry_delay=300, max_retries=5)
def store_data_task(self, url: str, content: str, task_id: str = None):
    """
    Celery task to store crawled data.
    Updates task status in Redis upon completion/failure.
    """
    print(f"Celery worker processing data for URL: {url} (Task ID: {task_id})")
    redis_client_sync = asyncio.run(get_redis_client()) # Get sync client for immediate update
    try:
        data_to_store = [{
            "url": url, 
            "content": content, 
            "crawled_at": datetime.datetime.now(),
            "task_id": task_id,
            "title": "Extracted Title Placeholder", 
            "metadata": {} 
        }]

        asyncio.run(_store_data_async(data_to_store))
        
        # Update status in Redis
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "completed",
            "completed_at": datetime.datetime.now().isoformat()
        }))
        print(f"Data for {url} stored successfully and status updated (Task ID: {task_id}).")
        return f"Data for {url} stored successfully."
    except Exception as e:
        print(f"Failed to store data for {url} (Task ID: {task_id}): {e}")
        # Update status in Redis as failed
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.datetime.now().isoformat()
        }))
        raise self.retry(exc=e)
    finally:
        asyncio.run(redis_client_sync.close()) # Close sync client

@app.task(name='tasks.update_task_status_failed', bind=True)
def update_task_status_failed_task(self, task_id: str, error_message: str):
    """
    Celery task to update task status to FAILED in Redis directly.
    Called by gRPC server if crawl fails before data storage.
    """
    print(f"Updating task {task_id} status to FAILED: {error_message}")
    redis_client_sync = asyncio.run(get_redis_client())
    try:
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "failed",
            "error": error_message,
            "completed_at": datetime.datetime.now().isoformat()
        }))
    except Exception as e:
        print(f"Failed to update task {task_id} status in Redis: {e}")
    finally:
        asyncio.run(redis_client_sync.close())


async def _store_data_async(data_items: list):
    """
    Asynchronously stores the crawled data to the chosen database.
    Now with PostgreSQL connection pooling.
    """
    if 'POSTGRES_URL' in os.environ and os.environ['POSTGRES_URL']: # Check if PostgreSQL is chosen
        pool = await get_pg_pool()
        async with pool.acquire() as conn: # Acquire connection from pool
            # Use executemany for bulk insert
            await conn.executemany('''
                INSERT INTO crawled_data(url, content, crawled_at, title, metadata, task_id)
                VALUES($1, $2, $3, $4, $5::jsonb, $6)
                ON CONFLICT (url) DO UPDATE SET
                    content = EXCLUDED.content,
                    crawled_at = EXCLUDED.crawled_at,
                    title = EXCLUDED.title,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW();
            ''', [(item['url'], item['content'], item['crawled_at'], item.get('title', ''), item.get('metadata', {}), item['task_id']) for item in data_items])
        print(f"Performed bulk insert/update of {len(data_items)} items to PostgreSQL.")

    elif 'MONGODB_URL' in os.environ and os.environ['MONGODB_URL']: # Check if MongoDB is chosen
        client = await get_mongo_client()
        db = client.crawler_db
        
        # Prepare bulk operations (Upsert for uniqueness on URL)
        bulk_ops = [
            InsertOne(item) # For simplicity, assuming new inserts. For upsert, use ReplaceOne or UpdateOne with upsert=True
            for item in data_items
        ]
        
        if bulk_ops:
            await db.crawled_pages.bulk_write(bulk_ops)
            print(f"Performed bulk insert of {len(data_items)} items to MongoDB.")
        
    else:
        print("No database URL configured in celery_workers/app/tasks.py. Data not stored.")

