import uvicorn
import asyncio
import os
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Gauge, Histogram, generate_latest

# --- Prometheus Metrics ---
# Define metrics
REQUESTS_TOTAL = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
GRPC_REQUESTS_TOTAL = Counter('grpc_requests_total', 'Total gRPC requests', ['service', 'method'])
CRAWL_TASK_DURATION = Histogram('crawl_task_duration_seconds', 'Duration of crawl tasks in seconds')
PROXY_POOL_SIZE = Gauge('proxy_pool_size', 'Current number of active proxies in pool') # This will be updated by proxy_manager
# --- End Prometheus Metrics ---

from app.grpc_server import serve as grpc_serve
from app.proxy_manager import main as proxy_manager_main
import redis.asyncio as aioredis # For scraping proxy pool size from Redis

# FastAPI app for REST endpoints (e.g., health check, metrics)
app_rest = FastAPI()

@app_rest.on_event("startup")
async def startup_event():
    # Start the gRPC server as a background task
    asyncio.create_task(grpc_serve())
    # Start the proxy manager as a background task
    asyncio.create_task(proxy_manager_main())
    print("FastAPI HTTP app started, gRPC server and proxy manager initiated as background tasks.")

@app_rest.get("/health")
async def health_check():
    REQUESTS_TOTAL.labels(method='GET', endpoint='/health').inc()
    return {"status": "ok", "service": "fastapi_crawler"}

# Custom metrics endpoint to include proxy_pool_size directly from Redis
@app_rest.get("/metrics")
async def metrics_endpoint():
    redis_client = await aioredis.from_url(f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}")
    try:
        current_proxy_size = await redis_client.scard("proxy_pool")
        PROXY_POOL_SIZE.set(current_proxy_size)
        return make_asgi_app()
    except Exception as e:
        print(f"Error getting proxy pool size for metrics: {e}")
        return make_asgi_app() # Still return other metrics even if proxy size fails

# This block is mainly for local development testing of both HTTP and gRPC.
if __name__ == "__main__":
    print("Running FastAPI via uvicorn directly (for development/testing).")
    uvicorn.run(app_rest, host="0.0.0.0", port=8000, workers=1) 
