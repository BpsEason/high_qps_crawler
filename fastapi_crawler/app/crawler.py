import aiohttp
import httpx
from fake_useragent import UserAgent
import asyncio
import redis.asyncio as aioredis
import random
import os
from twocaptcha import TwoCaptcha # Uncomment if using 2Captcha

# Environment variables (e.g., from .env file loaded by python-dotenv)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY") # Your 2Captcha API key

# Redis client for proxy management and URL deduplication
_redis_client = None

async def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
    return _redis_client

async def get_random_user_agent():
    ua = UserAgent()
    return ua.random

async def get_proxy():
    client = await get_redis_client()
    try:
        proxies_bytes = await client.smembers("proxy_pool")
        if not proxies_bytes:
            print("No proxies available in Redis pool. Using direct connection.")
            return None

        proxies = [p.decode('utf-8') for p in proxies_bytes]
        random.shuffle(proxies)

        for proxy in proxies:
            try:
                # Basic proxy health check (ping a known good site)
                async with httpx.AsyncClient(proxies={'http://': proxy, 'https://': proxy}, timeout=5) as test_client:
                    response = await test_client.get("http://httpbin.org/ip")
                    response.raise_for_status()
                print(f"Using healthy proxy: {proxy}")
                return proxy
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                print(f"Proxy {proxy} failed health check: {e}. Removing from pool.")
                await client.srem("proxy_pool", proxy) # Remove bad proxy
        
        print("All proxies failed health check or no healthy proxies found. Using direct connection.")
        return None

    except Exception as e:
        print(f"Error fetching proxy from Redis: {e}. Using direct connection.")
        return None

async def solve_captcha(image_data: bytes) -> str:
    """
    Integrates with 2Captcha to solve CAPTCHAs.
    Requires 2Captcha-python library and API key.
    """
    if not CAPTCHA_API_KEY:
        print("CAPTCHA_API_KEY not set. Cannot solve CAPTCHA.")
        return None
    try:
        solver = TwoCaptcha(apiKey=CAPTCHA_API_KEY)
        # Assuming image_data is the raw bytes of the CAPTCHA image
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: solver.normal(file=image_data))
        print(f"CAPTCHA solved: {result['code']}")
        return result['code']
    except Exception as e:
        print(f"Error solving CAPTCHA: {e}")
        return None

async def perform_crawl(url: str, task_id: str) -> str:
    user_agent = await get_random_user_agent()
    proxy = await get_proxy()
    
    await asyncio.sleep(random.uniform(0.1, 1.0)) # Reduced delay for higher QPS, adjusted min

    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.0,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    # Store cookies per session if needed (httpx client automatically handles this)
    async with httpx.AsyncClient(headers=headers, proxies={'http://': proxy, 'https://': proxy} if proxy else None, 
                                 timeout=30, follow_redirects=True) as client:
        try:
            print(f"Crawling: {url} (Task ID: {task_id}) with User-Agent: {user_agent}, Proxy: {proxy if proxy else 'None'}")
            response = await client.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Example: Basic URL deduplication (if needed at crawl time)
            redis_client = await get_redis_client()
            await redis_client.sadd("crawled_urls", url) # Add URL to a set for deduplication
            
            return response.text
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {url} (Task ID: {task_id}): {e}")
            raise
        except httpx.HTTPStatusError as e:
            print(f"Error response {e.response.status_code} while requesting {url} (Task ID: {task_id}): {e}")
            if e.response.status_code in [403, 429]: # Example: Forbidden, Too Many Requests
                print(f"Received {e.response.status_code}. Proxy might be blocked or more sophisticated anti-bot detected.")
                # You'd need logic here to extract CAPTCHA image from response.content
                # For demonstration, assume CAPTCHA image is available or a specific HTML pattern.
                # Example placeholder for CAPTCHA detection and solving:
                # if "captcha" in e.response.text.lower():
                #     print("CAPTCHA detected, attempting to solve...")
                #     # You'd need to parse the response to get the actual CAPTCHA image bytes
                #     # For this example, we'll just show the call, without actual image extraction:
                #     # solved_text = await solve_captcha(b"dummy_image_data_here")
                #     # if solved_text:
                #     #     print(f"CAPTCHA solved: {solved_text}. You might need to retry the request with the solved text.")
                #     # else:
                #     #     print("Failed to solve CAPTCHA.")
            raise

# For local testing of crawler.py
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # Load .env variables for testing

    async def test_crawl():
        test_url = "http://httpbin.org/get" # A simple test URL
        test_task_id = "test_task_123"
        try:
            content = await perform_crawl(test_url, test_task_id)
            print(f"Successfully crawled {test_url}. Content snippet:\n{content[:500]}...")
        except Exception as e:
            print(f"Test crawl failed: {e}")

    asyncio.run(test_crawl())
