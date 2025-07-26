import aiohttp
import redis.asyncio as aioredis
import asyncio
import os
import random

# Environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# Example for a free proxy API. Replace with a robust, reliable proxy source in production.
# PROXY_API_URL = os.getenv("PROXY_API_URL", "http://pubproxy.com/api/proxy?limit=50&format=txt&http=true&level=anonymous")
# Using 98IP example structure as per discussion, though actual API might differ for free tiers
# For demonstration, let's use a dummy URL that returns a simple list of proxies.
# In a real scenario, you'd integrate with a service like 98IP or BrightData.
# Dummy API URL for demonstration (replace with actual proxy API)
DUMMY_PROXY_API_URL = "http://example.com/api/proxies" 
# For testing locally without an external API:
# You can generate a local HTTP server that returns a list of proxies, or just hardcode some
# For the sake of this script, we'll assume a list of proxies is retrieved.

async def get_redis_client():
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")

async def fetch_proxies_from_api(api_url: str) -> list:
    """Fetches proxies from an external API."""
    try:
        async with aiohttp.ClientSession() as session:
            # Example for a simple text response with one proxy per line
            # async with session.get(api_url, timeout=10) as resp:
            #     resp.raise_for_status()
            #     text = await resp.text()
            #     proxies = [p.strip() for p in text.split('\n') if p.strip()]
            
            # Example for a JSON response (like some commercial APIs)
            # For 98IP example, assuming it returns {"data": [{"ip": "...", "port": "..."}, ...]}
            # For now, let's just return some dummy proxies for script execution.
            print(f"Fetching proxies from {api_url}...")
            # Simulate API call
            await asyncio.sleep(2) # Simulate network delay
            dummy_proxies = [
                "http://192.168.1.1:8080",
                "http://192.168.1.2:3128",
                "http://192.168.1.3:80",
                # Add more dummy proxies or replace with actual API call
            ]
            print(f"Fetched {len(dummy_proxies)} dummy proxies.")
            return dummy_proxies
    except aiohttp.ClientError as e:
        print(f"Error fetching proxies from API {api_url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during proxy fetch: {e}")
        return []

async def health_check_proxy(proxy: str) -> bool:
    """Performs a quick health check on a single proxy."""
    try:
        async with httpx.AsyncClient(proxies={'http://': proxy, 'https://': proxy}, timeout=5) as client:
            response = await client.get("http://httpbin.org/ip")
            response.raise_for_status()
            return True
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False

async def update_proxy_pool():
    """
    Fetches new proxies, health checks them, and updates the Redis proxy_pool.
    """
    redis_client = await get_redis_client()
    try:
        print("Starting proxy pool update cycle...")
        new_proxies = await fetch_proxies_from_api(os.getenv("PROXY_API_URL", DUMMY_PROXY_API_URL))
        
        healthy_proxies = set()
        if new_proxies:
            # Concurrently check health of new proxies
            tasks = [health_check_proxy(p) for p in new_proxies]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for proxy, result in zip(new_proxies, results):
                if result is True:
                    healthy_proxies.add(proxy)
                else:
                    print(f"New proxy {proxy} failed health check or returned error: {result}")
        
        # Clear existing proxies and add new healthy ones
        await redis_client.delete("proxy_pool")
        if healthy_proxies:
            await redis_client.sadd("proxy_pool", *list(healthy_proxies))
            print(f"Updated Redis proxy_pool with {len(healthy_proxies)} healthy proxies.")
        else:
            print("No healthy proxies found to add to the pool.")

        # Update Prometheus Gauge
        await redis_client.set("proxy_pool_size", len(healthy_proxies)) # Store size in Redis for Prometheus to scrape
        
    except Exception as e:
        print(f"Failed to update proxy pool in Redis: {e}")
    finally:
        await redis_client.close()

async def main():
    # Initial update
    await update_proxy_pool()
    # Schedule periodic updates
    while True:
        await asyncio.sleep(int(os.getenv("PROXY_UPDATE_INTERVAL_SECONDS", 3600))) # Default: hourly update
        await update_proxy_pool()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
