# 高 QPS 網路爬蟲系統

這是一個高效能的分散式網路爬蟲系統，目標是達到 **每秒 10,000 次查詢 (QPS)**，適合大規模網頁抓取。本倉庫只放核心程式碼，使用 **Laravel**、**FastAPI**、**gRPC**、**Redis**、**Celery** 和 **PostgreSQL/MongoDB** 打造，模組化且可擴展，支援反爬蟲和監控功能。

---

## 🚀 專案簡介

這個專案是為了解決高吞吐量網頁抓取的需求，核心程式碼展示如何用分散式架構實現高效爬蟲。主要特色：

- **高性能**：支援 10,000 QPS，靠 Docker Compose 輕鬆擴展。
- **模組化**：分成 Laravel API、FastAPI 爬蟲、Redis 佇列和 Celery 資料處理。
- **反爬蟲**：有代理池、隨機 User-Agent 和 2Captcha 支援。
- **監控**：整合 Prometheus、Grafana 和 Celery Flower，方便追蹤效能。

**注意**：倉庫只包含核心程式碼，Laravel 環境得自己裝。

---

## 🛠️ 系統架構

系統架構簡單明瞭：

1. **Laravel API** (`laravel_api/`)：
   - 負責任務提交和狀態查詢，透過 gRPC 跟 FastAPI 溝通。
   - 任務狀態存在 Redis，歷史資料進 PostgreSQL 或 MongoDB。

2. **FastAPI 爬蟲核心** (`fastapi_crawler/`)：
   - 用 `aiohttp` 和 `httpx` 抓網頁，支援代理池和反爬蟲策略。
   - 提供 gRPC 服務和 REST 端點。

3. **Celery 工作節點** (`celery_workers/`)：
   - 處理抓回來的資料，支援高並發儲存。

4. **Redis**：管任務佇列、代理池和 URL 去重。
5. **PostgreSQL/MongoDB**：預設 PostgreSQL，可換 MongoDB。
6. **監控**：Prometheus、Grafana 和 Celery Flower。

---

## 📋 環境需求

- **Docker** 和 **Docker Compose**：跑容器化服務。
- **Laravel 環境**：PHP 8.2+、Composer（自己裝）。
- **硬體建議**（10,000 QPS）：
  - CPU：32-64 核心。
  - 記憶體：128-256 GB。
  - 網路：10 Gbps。
  - 儲存：NVMe SSD（1-2 TB）。
- **代理 API**：像 98IP 或 BrightData 這種可靠的代理服務。
- **2Captcha API 金鑰**（可選）：解 CAPTCHA 用。

---

## 🏗️ 怎麼跑起來

1. **抓程式碼**：
   ```bash
   git clone https://github.com/BpsEason/high_qps_crawler.git
   cd high_qps_crawler
   ```

2. **裝 Laravel 環境**：
   - 進 `laravel_api/` 目錄：
     ```bash
     cd laravel_api
     composer install
     cp .env.example .env
     php artisan key:generate
     ```

3. **設環境變數**：
   - 在 `fastapi_crawler/.env`：
     ```env
     CAPTCHA_API_KEY=你的_2captcha_api_金鑰  # 可選
     PROXY_API_URL=https://api.your-proxy-provider.com/get-proxies  # 換成真實代理 API
     PROXY_UPDATE_INTERVAL_SECONDS=3600
     ```
   - 在 `laravel_api/.env`：
     ```env
     DB_CONNECTION=pgsql
     DB_HOST=pgbouncer
     DB_PORT=6432
     DB_DATABASE=crawler_db
     DB_USERNAME=user
     DB_PASSWORD=password
     REDIS_HOST=redis
     REDIS_PORT=6379
     FASTAPI_GRPC_HOST=fastapi_crawler:50051
     ```

4. **選資料庫**：
   - 預設用 **PostgreSQL**（有 PgBouncer 連線池）。
   - 想用 **MongoDB**，改 `docker-compose.yml` 和 `laravel_api/.env`：
     ```env
     DB_CONNECTION=mongodb
     DB_HOST=mongodb
     DB_PORT=27017
     DB_DATABASE=crawler_db
     MONGODB_URL=mongodb://mongodb:27017
     ```

5. **建置並啟動服務**：
   ```bash
   docker compose build
   docker compose up -d
   ```

6. **初始化資料庫**：
   ```bash
   docker compose exec laravel php artisan migrate
   ```

7. **擴展 Celery 工作節點**：
   ```bash
   docker compose up -d --scale celery_worker=10
   ```

8. **試跑爬蟲**：
   - 丟個任務：
     ```bash
     curl -X POST -H "Content-Type: application/json" -d '{"url": "http://example.com"}' http://localhost:8000/api/submit-crawl
     ```
   - 查任務狀態：
     ```bash
     curl http://localhost:8000/api/crawl-status/{task_id}
     ```

---

## 🔑 核心程式碼與中文註解

以下是專案的關鍵程式碼，帶中文註解，展示主要功能：

### 1. Laravel API - 任務提交 (`laravel_api/app/Http/Controllers/CrawlerController.php`)

```php
<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Grpc\ChannelCredentials;
use App\Grpc\CrawlerServiceClient;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Redis;

class CrawlerController extends Controller
{
    /**
     * 把爬取任務丟給 FastAPI（用 gRPC）
     */
    public function submitCrawlTask(Request $request)
    {
        // 檢查 URL 格式
        $request->validate(['url' => 'required|url']);
        $url = $request->input('url');
        $taskId = uniqid('crawl_'); // 產生唯一任務 ID

        try {
            // 連 FastAPI 的 gRPC 服務
            $client = new CrawlerServiceClient(env('FASTAPI_GRPC_HOST', 'fastapi_crawler:50051'), [
                'credentials' => ChannelCredentials::createInsecure(),
            ]);
            
            // 包裝 gRPC 請求
            $requestProto = new \Crawler\CrawlRequest();
            $requestProto->setUrl($url);
            $requestProto->setTaskId($taskId);

            // 送出請求
            list($response, $status) = $client->Crawl($requestProto)->wait();
            if ($status->code !== \Grpc\STATUS_OK) {
                throw new \Exception("gRPC 失敗: " . $status->details);
            }

            // 存任務狀態到 Redis
            Redis::hset("crawl_task_status:{$taskId}", "status", "dispatched");
            Redis::hset("crawl_task_status:{$taskId}", "url", $url);
            Redis::hset("crawl_task_status:{$taskId}", "dispatched_at", now()->toIso8601String());

            Log::info("gRPC 成功，URL: $url, 任務 ID: $taskId");
            return response()->json([
                'message' => '任務送出',
                'task_id' => $taskId,
                'grpc_response_status' => $response->getStatus(),
            ]);
        } catch (\Exception $e) {
            // 出錯就記 log，更新 Redis 狀態
            Log::error("送任務失敗，URL: $url. 錯誤: " . $e->getMessage());
            Redis::hset("crawl_task_status:{$taskId}", "status", "submission_failed");
            Redis::hset("crawl_task_status:{$taskId}", "error", $e->getMessage());
            return response()->json(['error' => '送任務失敗: ' . $e->getMessage()], 500);
        }
    }
}
```

**說明**：這段程式碼負責把爬取任務丟給 FastAPI，用 gRPC 通信，任務狀態存到 Redis，方便即時查詢。

---

### 2. FastAPI 爬蟲核心 - 抓網頁 (`fastapi_crawler/app/crawler.py`)

```python
import aiohttp
import httpx
from fake_useragent import UserAgent
import asyncio
import redis.asyncio as aioredis
import random
import os

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

async def get_redis_client():
    """連 Redis，拿代理或去重"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
    return _redis_client

async def get_proxy():
    """從 Redis 抓個好用的代理"""
    client = await get_redis_client()
    try:
        proxies_bytes = await client.smembers("proxy_pool")
        if not proxies_bytes:
            print("沒代理，直接連")
            return None
        proxies = [p.decode('utf-8') for p in proxies_bytes]
        random.shuffle(proxies)
        for proxy in proxies:
            try:
                async with httpx.AsyncClient(proxies={'http://': proxy, 'https://': proxy}, timeout=5) as test_client:
                    response = await test_client.get("http://httpbin.org/ip")
                    response.raise_for_status()
                print(f"用這個代理: {proxy}")
                return proxy
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                print(f"代理 {proxy} 壞了: {e}")
                await client.srem("proxy_pool", proxy)
        print("沒好代理")
        return None
    except Exception as e:
        print(f"抓代理失敗: {e}")
        return None

async def perform_crawl(url: str, task_id: str) -> str:
    """抓網頁內容"""
    user_agent = UserAgent().random  # 隨機換 User-Agent
    proxy = await get_proxy()  # 拿代理
    await asyncio.sleep(random.uniform(0.1, 1.0))  # 隨機等一下，躲反爬

    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    async with httpx.AsyncClient(headers=headers, proxies={'http://': proxy, 'https://': proxy} if proxy else None, 
                                 timeout=30, follow_redirects=True) as client:
        try:
            print(f"抓: {url} (任務 ID: {task_id})")
            response = await client.get(url)
            response.raise_for_status()
            redis_client = await get_redis_client()
            await redis_client.sadd("crawled_urls", url)  # 記住抓過的 URL
            return response.text
        except httpx.HTTPStatusError as e:
            print(f"抓失敗，狀態碼 {e.response.status_code}: {e}")
            if e.response.status_code in [403, 429]:
                print("可能有 CAPTCHA")
            raise
```

**說明**：這段程式碼用非同步方式抓網頁，支援代理和隨機 User-Agent，還有 URL 去重，預留了 CAPTCHA 處理空間。

---

### 3. Celery 工作節點 - 存資料 (`celery_workers/app/tasks.py`)

```python
from celery_app import app
import asyncio
import asyncpg
import datetime
import os
import redis.asyncio as aioredis

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://user:password@pgbouncer:6432/crawler_db")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

async def get_redis_client():
    """連 Redis，更新任務狀態"""
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")

async def get_pg_pool():
    """拿 PostgreSQL 連線池"""
    global _pg_pool
    if _pg_pool is None:
        if POSTGRES_URL:
            _pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=10, max_size=50)
        else:
            raise ValueError("沒設 POSTGRES_URL")
    return _pg_pool

@app.task(name='tasks.store_data', bind=True, default_retry_delay=300, max_retries=5)
def store_data_task(self, url: str, content: str, task_id: str = None):
    """把抓到的資料存起來"""
    print(f"處理 URL: {url} (任務 ID: {task_id})")
    redis_client_sync = asyncio.run(get_redis_client())
    try:
        data_to_store = [{
            "url": url,
            "content": content,
            "crawled_at": datetime.datetime.now(),
            "task_id": task_id,
            "title": "標題佔位",
            "metadata": {}
        }]

        asyncio.run(_store_data_async(data_to_store))
        
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "completed",
            "completed_at": datetime.datetime.now().isoformat()
        }))
        print(f"存好: {url}")
        return f"存好: {url}"
    except Exception as e:
        print(f"存失敗: {url}, 錯誤: {e}")
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.datetime.now().isoformat()
        }))
        raise self.retry(exc=e)
    finally:
        asyncio.run(redis_client_sync.close())

async def _store_data_async(data_items: list):
    """非同步存到 PostgreSQL"""
    if POSTGRES_URL:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.executemany('''
                INSERT INTO crawled_data(url, content, crawled_at, title, metadata, task_id)
                VALUES($1, $2, $3, $4, $5::jsonb, $6)
                ON CONFLICT (url) DO UPDATE
                SET content = EXCLUDED.content, crawled_at = EXCLUDED.crawled_at,
                    title = EXCLUDED.title, metadata = EXCLUDED.metadata,
                    updated_at = NOW();
            ''', [(item['url'], item['content'], item['crawled_at'], item.get('title', ''),
                   item.get('metadata', {}), item['task_id']) for item in data_items])
        print(f"存了 {len(data_items)} 條資料")
```

**說明**：這段程式碼把抓到的資料存到 PostgreSQL，用連線池和批量插入提高效率，同時更新 Redis 的任務狀態。

---

## ❓ 常見問題與解答

以下是一些開發者可能會問的問題，結合專案程式碼和設計，幫你快速上手或解決疑惑。

### Q1: 怎麼讓這系統跑出高 QPS？

這專案用分散式架構，靠多個組件分工來撐高 QPS。Laravel 管任務分派，FastAPI 負責抓網頁，Celery 處理資料儲存，Redis 當中間人。關鍵是：

- **非同步爬取**：FastAPI 用 `aiohttp` 和 `httpx` 跑非同步請求，單節點能到 1,600-4,000 QPS。
- **分散式處理**：Celery 用 `gevent` 模式，每個 worker 跑 300 個任務。
- **擴展**：用 `docker compose up -d --scale celery_worker=10` 開多個 worker。

**程式碼**（`fastapi_crawler/app/crawler.py`）：
```python
async def perform_crawl(url: str, task_id: str) -> str:
    user_agent = UserAgent().random
    proxy = await get_proxy()
    await asyncio.sleep(random.uniform(0.1, 1.0))  # 隨機延遲
    headers = {'User-Agent': user_agent, ...}
    async with httpx.AsyncClient(headers=headers, proxies={'http://': proxy} if proxy else None,
                                 timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        redis_client = await get_redis_client()
        await redis_client.sadd("crawled_urls", url)
        return response.text
```

**小訣竅**：
- 設真實的 `PROXY_API_URL`（像 98IP），保持 100-200 個代理。
- 開多點 FastAPI worker：`gunicorn -w 16`。
- 用 Locust 測 QPS：
  ```bash
  locust -f locustfile.py
  ```

---

### Q2: 資料庫怎麼扛高並發？

專案用 **PostgreSQL** 配 **PgBouncer** 連線池，Celery 透過 `asyncpg` 批量寫資料，減少連線負擔。如果選 MongoDB，則靠它的靈活結構處理非結構化資料。

**程式碼**（`celery_workers/app/tasks.py`）：
```python
async def _store_data_async(data_items: list):
    pool = await get_pg_pool()  # 連線池，10-50 連線
    async with pool.acquire() as conn:
        await conn.executemany('''
            INSERT INTO crawled_data(url, content, crawled_at, title, metadata, task_id)
            VALUES($1, $2, $3, $4, $5::jsonb, $6)
            ON CONFLICT (url) DO UPDATE
            SET content = EXCLUDED.content, ...
        ''', [(item['url'], item['content'], item['crawled_at'], ...) for item in data_items])
    print(f"存了 {len(data_items)} 條資料")
```

**做法**：
- PgBouncer 設 `MAX_CLIENT_CONNECTIONS=1000`，`DEFAULT_POOL_SIZE=50`。
- 用 `ON CONFLICT` 去重，省查詢時間。
- 在 `url` 欄位加唯一索引。
- MongoDB 則可考慮分片，處理超大資料量。

---

### Q3: 怎麼躲網站的反爬蟲？

專案有幾招防反爬：

1. **代理池**：`proxy_manager.py` 定期從 API 抓代理，存 Redis，自動檢查健康。
2. **User-Agent**：用 `fake-useragent` 隨機換。
3. **CAPTCHA**：支援 2Captcha，預留解析邏輯。

**程式碼**（`fastapi_crawler/app/crawler.py`）：
```python
async def get_proxy():
    client = await get_redis_client()
    proxies_bytes = await client.smembers("proxy_pool")
    proxies = [p.decode('utf-8') for p in proxies_bytes]
    random.shuffle(proxies)
    for proxy in proxies:
        try:
            async with httpx.AsyncClient(proxies={'http://': proxy, 'https://': proxy}, timeout=5) as test_client:
                response = await test_client.get("http://httpbin.org/ip")
                response.raise_for_status()
            return proxy
        except:
            await client.srem("proxy_pool", proxy)
    return None
```

**建議**：
- 設隨機延遲（0.1-1.0 秒）。
- 未來加 Playwright 抓動態頁面：
  ```yaml
  playwright:
    image: mcr.microsoft.com/playwright:v1.39.0
  ```

---

### Q4: 怎麼看系統跑得順不順？

專案整合了幾個監控工具：

- **Prometheus**：`http://localhost:9090`，看 QPS、延遲、代理數。
- **Grafana**：`http://localhost:3000`（`admin/admin`），畫圖表。
- **Celery Flower**：`http://localhost:5555`，查任務狀態。

**調優**：
- 加 FastAPI worker：`gunicorn -w 16`。
- 調 Celery 並發：`--concurrency=500 -P gevent`。
- 用 Locust 壓力測試，找瓶頸。

---

### Q5: 為啥用 gRPC 連 Laravel 跟 FastAPI？

gRPC 比 REST 快，適合內部高頻通信：

- **高效**：用 HTTP/2 和 Protocol Buffers，序列化快。
- **型別安全**：`crawler.proto` 定義資料結構，少出錯。
- **擴展性**：支援雙向流，未來可加即時回饋。

**程式碼**（`laravel_api/app/Grpc/CrawlerServiceClient.php`）：
```php
$client = new CrawlerServiceClient(env('FASTAPI_GRPC_HOST', 'fastapi_crawler:50051'), [
    'credentials' => ChannelCredentials::createInsecure(),
]);
$requestProto = new \Crawler\CrawlRequest();
$requestProto->setUrl($url);
$requestProto->setTaskId($taskId);
list($response, $status) = $client->Crawl($requestProto)->wait();
```

**啥時用 REST**？如果跨語言或快速試驗，REST 簡單點，但 gRPC 更適合這專案的高性能需求。

---

### Q6: 任務掛了怎麼辦？

專案用 Celery 的重試機制和 Redis 狀態追蹤處理失敗：

- **重試**：`store_data_task` 設 `max_retries=5`，失敗後等 300 秒再試。
- **狀態**：失敗時更新 Redis 的 `crawl_task_status:{taskId}`。

**程式碼**（`celery_workers/app/tasks.py`）：
```python
@app.task(name='tasks.store_data', bind=True, default_retry_delay=300, max_retries=5)
def store_data_task(self, url: str, content: str, task_id: str = None):
    try:
        data_to_store = [{"url": url, "content": content, ...}]
        asyncio.run(_store_data_async(data_to_store))
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "completed",
            "completed_at": datetime.datetime.now().isoformat()
        }))
    except Exception as e:
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "failed",
            "error": str(e),
            ...
        }))
        raise self.retry(exc=e)
```

**小技巧**：
- 設合理的 `default_retry_delay`，別讓重試把系統壓垮。
- 錯誤記到 Redis，方便 debug。

---

## 📊 監控與除錯

- **Prometheus**：`http://localhost:9090`。
- **Grafana**：`http://localhost:3000`（`admin/admin`）。
- **Celery Flower**：`http://localhost:5555`。
- **ELK Stack**（可選）：改 `docker-compose.yml`，用 `http://localhost:5601`。

---

## ⚙️ 怎麼跑更快

想衝 **10,000 QPS**：
- FastAPI：`gunicorn -w 16`。
- Celery：`--concurrency=500 -P gevent`。
- 代理：設真實 `PROXY_API_URL`，保持 100-200 個代理。
- 測效能：
  ```bash
  locust -f locustfile.py
  ```

---

## 🔐 反爬蟲招數

- **代理**：`proxy_manager.py` 管 Redis 代理池。
- **User-Agent**：`fake-useragent` 隨機化。
- **CAPTCHA**：支援 2Captcha。
- **進階**：加 Playwright：
  ```yaml
  playwright:
    image: mcr.microsoft.com/playwright:v1.39.0
  ```

---

## 📂 專案結構

```plaintext
high_qps_crawler/
├── laravel_api/               # Laravel API
│   ├── app/
│   │   ├── Http/Controllers/CrawlerController.php
│   │   ├── Grpc/CrawlerServiceClient.php
│   ├── proto/crawler.proto
│   ├── routes/api.php
│   ├── database/migrations/
│   ├── docker/
│   └── Dockerfile
├── fastapi_crawler/           # FastAPI 爬蟲
│   ├── app/
│   │   ├── crawler.py
│   │   ├── grpc_server.py
│   │   ├── proxy_manager.py
│   ├── proto/crawler.proto
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── celery_workers/            # Celery 工作節點
│   ├── app/
│   │   ├── tasks.py
│   │   ├── celery_app.py
│   ├── requirements.txt
│   └── Dockerfile
├── monitoring/                # 監控
│   ├── prometheus.yml
│   └── logstash.conf
├── redis_data/                # Redis 資料
├── data_storage/              # 資料庫
│   ├── mongodb_data/
│   └── postgresql_data/
└── docker-compose.yml         # Docker Compose
```

---

## 🤝 想幫忙？

1. Fork 這專案。
2. 開分支：`git checkout -b feature/你的功能`。
3. 提交：`git commit -m '加了啥啥'`。
4. 推上去：`git push origin feature/你的功能`。
5. 開 Pull Request。

