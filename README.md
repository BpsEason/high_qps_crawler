# 高 QPS 網路爬蟲系統

這是一個高效能的分散式網路爬蟲系統，設計目標為實現 **每秒 10,000 次查詢 (QPS)**，適用於大規模網頁抓取。本倉庫僅包含核心程式碼，採用 **Laravel**、**FastAPI**、**gRPC**、**Redis**、**Celery** 和 **PostgreSQL/MongoDB** 構建，具備模組化、可擴展和生產就緒特性，支援反爬蟲和監控功能。

---

## 🚀 專案概述

本專案提供一個分散式爬蟲系統的核心程式碼，支援高 QPS 並確保穩定性。主要功能包括：

- **高吞吐量**：通過 Docker Compose 水平擴展，支援 10,000 QPS。
- **模組化架構**：分離 API 管理 (Laravel)、爬蟲核心 (FastAPI)、任務佇列 (Redis) 和資料儲存 (PostgreSQL/MongoDB)。
- **反爬蟲措施**：支援代理池、隨機 User-Agent 和 2Captcha 解決 CAPTCHA。
- **監控**：整合 Prometheus、Grafana 和 Celery Flower。

**注意**：本倉庫僅包含關鍵程式碼，Laravel 基礎環境需自行安裝。

---

## 🛠️ 系統架構

系統包含以下核心組件：

1. **Laravel API** (`laravel_api/`)：
   - 處理任務提交和狀態查詢，通過 gRPC 與 FastAPI 通信。
   - 使用 Redis 儲存任務狀態，PostgreSQL/MongoDB 儲存歷史數據。

2. **FastAPI 爬蟲核心** (`fastapi_crawler/`)：
   - 執行非同步 HTTP 請求，管理代理池和反爬蟲措施。
   - 提供 gRPC 伺服器和 REST 端點。

3. **Celery 工作節點** (`celery_workers/`)：
   - 處理分散式資料儲存任務，支援高並發。

4. **Redis**：管理任務佇列、代理池和 URL 去重。
5. **PostgreSQL/MongoDB**：預設 PostgreSQL，支援 MongoDB。
6. **監控**：Prometheus、Grafana 和 Celery Flower。

---

## 📋 前置需求

- **Docker** 和 **Docker Compose**：用於容器化部署。
- **Laravel 環境**：PHP 8.2+、Composer（需自行安裝）。
- **硬體**（建議用於 10,000 QPS）：
  - CPU：32-64 核心。
  - 記憶體：128-256 GB。
  - 網路：10 Gbps。
  - 儲存：NVMe SSD（1-2 TB）。
- **代理 API**：可靠的代理提供商（如 98IP、BrightData）。
- **2Captcha API 金鑰**（可選）：用於 CAPTCHA 解決。

---

## 🏗️ 部署步驟

1. **克隆倉庫**：
   ```bash
   git clone https://github.com/BpsEason/high_qps_crawler.git
   cd high_qps_crawler
   ```

2. **安裝 Laravel 基礎環境**：
   - 在 `laravel_api/` 目錄下，安裝 Laravel 依賴：
     ```bash
     cd laravel_api
     composer install
     cp .env.example .env
     php artisan key:generate
     ```
   - 配置 `.env` 中的資料庫和 Redis 連線（見下文）。

3. **配置環境變數**：
   - 在 `fastapi_crawler/.env` 中添加：
     ```env
     CAPTCHA_API_KEY=你的_2captcha_api_金鑰  # 可選
     PROXY_API_URL=https://api.your-proxy-provider.com/get-proxies  # 真實代理 API
     PROXY_UPDATE_INTERVAL_SECONDS=3600  # 代理池更新間隔（秒）
     ```
   - 在 `laravel_api/.env` 中配置：
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

4. **選擇資料庫**：
   - 預設：**PostgreSQL**（搭配 PgBouncer）。
   - 若使用 **MongoDB**，在 `docker-compose.yml` 中：
     - 註釋掉 `postgresql` 和 `pgbouncer`。
     - 取消 `mongodb` 服務註釋。
     - 更新 `laravel_api/.env`：
       ```env
       DB_CONNECTION=mongodb
       DB_HOST=mongodb
       DB_PORT=27017
       DB_DATABASE=crawler_db
       MONGODB_URL=mongodb://mongodb:27017
       ```

5. **構建並運行服務**：
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

8. **測試爬蟲**：
   - 提交任務：
     ```bash
     curl -X POST -H "Content-Type: application/json" -d '{"url": "http://example.com"}' http://localhost:8000/api/submit-crawl
     ```
   - 查詢狀態：
     ```bash
     curl http://localhost:8000/api/crawl-status/{task_id}
     ```

---

## 🔑 關鍵程式碼與中文註解

以下是核心程式碼片段，包含中文註解：

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
     * 提交爬取任務至 FastAPI（通過 gRPC）
     */
    public function submitCrawlTask(Request $request)
    {
        // 驗證輸入 URL
        $request->validate(['url' => 'required|url']);
        $url = $request->input('url');
        $taskId = uniqid('crawl_'); // 生成唯一任務 ID

        try {
            // 初始化 gRPC 客戶端
            $client = new CrawlerServiceClient(env('FASTAPI_GRPC_HOST', 'fastapi_crawler:50051'), [
                'credentials' => ChannelCredentials::createInsecure(),
            ]);
            
            // 創建 gRPC 請求
            $requestProto = new \Crawler\CrawlRequest();
            $requestProto->setUrl($url);
            $requestProto->setTaskId($taskId);

            // 發送 gRPC 請求
            list($response, $status) = $client->Crawl($requestProto)->wait();
            if ($status->code !== \Grpc\STATUS_OK) {
                throw new \Exception("gRPC 調用失敗: " . $status->details);
            }

            // 儲存任務狀態至 Redis
            Redis::hset("crawl_task_status:{$taskId}", "status", "dispatched");
            Redis::hset("crawl_task_status:{$taskId}", "url", $url);
            Redis::hset("crawl_task_status:{$taskId}", "dispatched_at", now()->toIso8601String());

            Log::info("gRPC 成功，URL: $url, 任務 ID: $taskId");
            return response()->json([
                'message' => '任務已提交',
                'task_id' => $taskId,
                'grpc_response_status' => $response->getStatus(),
            ]);
        } catch (\Exception $e) {
            // 記錄錯誤並更新狀態
            Log::error("提交失敗，URL: $url. 錯誤: " . $e->getMessage());
            Redis::hset("crawl_task_status:{$taskId}", "status", "submission_failed");
            Redis::hset("crawl_task_status:{$taskId}", "error", $e->getMessage());
            return response()->json(['error' => '提交失敗: ' . $e->getMessage()], 500);
        }
    }
}
```

**說明**：處理任務提交，通過 gRPC 與 FastAPI 通信，並使用 Redis 儲存任務狀態。

---

### 2. FastAPI 爬蟲核心 - 網頁抓取 (`fastapi_crawler/app/crawler.py`)

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
    """獲取 Redis 連線"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
    return _redis_client

async def get_proxy():
    """從 Redis 選擇有效代理"""
    client = await get_redis_client()
    try:
        proxies_bytes = await client.smembers("proxy_pool")
        if not proxies_bytes:
            print("無可用代理，使用直接連線")
            return None
        proxies = [p.decode('utf-8') for p in proxies_bytes]
        random.shuffle(proxies)
        for proxy in proxies:
            try:
                async with httpx.AsyncClient(proxies={'http://': proxy, 'https://': proxy}, timeout=5) as test_client:
                    response = await test_client.get("http://httpbin.org/ip")
                    response.raise_for_status()
                print(f"使用代理: {proxy}")
                return proxy
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                print(f"代理 {proxy} 失敗: {e}")
                await client.srem("proxy_pool", proxy)
        print("無有效代理")
        return None
    except Exception as e:
        print(f"獲取代理失敗: {e}")
        return None

async def perform_crawl(url: str, task_id: str) -> str:
    """執行網頁爬取"""
    user_agent = UserAgent().random
    proxy = await get_proxy()
    await asyncio.sleep(random.uniform(0.1, 1.0))  # 隨機延遲

    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.0,image/webp,*/*;q=0.8',
    }
    
    async with httpx.AsyncClient(headers=headers, proxies={'http://': proxy, 'https://': proxy} if proxy else None, 
                                 timeout=30, follow_redirects=True) as client:
        try:
            print(f"爬取: {url} (任務 ID: {task_id})")
            response = await client.get(url)
            response.raise_for_status()
            redis_client = await get_redis_client()
            await redis_client.sadd("crawled_urls", url)  # URL 去重
            return response.text
        except httpx.HTTPStatusError as e:
            print(f"爬取失敗，狀態碼 {e.response.status_code}: {e}")
            if e.response.status_code in [403, 429]:
                print("可能需要 CAPTCHA 解決")
            raise
```

**說明**：實現非同步爬取，支援代理和 User-Agent 隨機化，預留 CAPTCHA 解決邏輯。

---

### 3. Celery 工作節點 - 資料儲存 (`celery_workers/app/tasks.py`)

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
    """獲取 Redis 連線"""
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")

async def get_pg_pool():
    """獲取 PostgreSQL 連線池"""
    global _pg_pool
    if _pg_pool is None:
        if POSTGRES_URL:
            _pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=10, max_size=50)
        else:
            raise ValueError("未設置 POSTGRES_URL")
    return _pg_pool

@app.task(name='tasks.store_data', bind=True, default_retry_delay=300, max_retries=5)
def store_data_task(self, url: str, content: str, task_id: str = None):
    """儲存爬取數據"""
    print(f"處理 URL: {url} (任務 ID: {task_id})")
    redis_client_sync = asyncio.run(get_redis_client())
    try:
        data_to_store = [{
            "url": url,
            "content": content,
            "crawled_at": datetime.datetime.now(),
            "task_id": task_id,
            "title": "標題佔位符",
            "metadata": {}
        }]

        asyncio.run(_store_data_async(data_to_store))
        
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "completed",
            "completed_at": datetime.datetime.now().isoformat()
        }))
        print(f"儲存成功: {url}")
        return f"儲存成功: {url}"
    except Exception as e:
        print(f"儲存失敗: {url}, 錯誤: {e}")
        asyncio.run(redis_client_sync.hset(f"crawl_task_status:{task_id}", mapping={
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.datetime.now().isoformat()
        }))
        raise self.retry(exc=e)
    finally:
        asyncio.run(redis_client_sync.close())

async def _store_data_async(data_items: list):
    """非同步儲存至 PostgreSQL"""
    if POSTGRES_URL:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
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
        print(f"批量插入 {len(data_items)} 條數據")
```

**說明**：處理資料儲存，使用 PostgreSQL 連線池，更新 Redis 任務狀態。

---

## 📊 監控與除錯

- **Prometheus**：`http://localhost:9090`，監控 QPS 和代理池大小。
- **Grafana**：`http://localhost:3000`（帳號/密碼：`admin/admin`），可視化儀表板。
- **Celery Flower**：`http://localhost:5555`，監控任務狀態。
- **ELK Stack**（可選）：取消 `docker-compose.yml` 中相關服務的註釋，訪問 `http://localhost:5601`。

---

## ⚙️ 性能調優

為實現 **10,000 QPS**：

1. **擴展服務**：
   - FastAPI 工作進程：
     ```yaml
     command: gunicorn -k uvicorn.workers.UvicornWorker -w 16 main:app_rest --bind 0.0.0.0:8000
     ```
   - Celery 並發度：
     ```yaml
     command: celery -A celery_app worker --loglevel=info --concurrency=500 -P gevent
     ```

2. **代理池**：
   - 配置有效 `PROXY_API_URL`（如 98IP），確保 100-200 個代理。
   - 縮短 `PROXY_UPDATE_INTERVAL_SECONDS` 至 1800 秒。

3. **壓力測試**：
   - 使用 Locust：
     ```python
     # locustfile.py
     from locust import HttpUser, task, between

     class CrawlerUser(HttpUser):
         wait_time = between(0.1, 0.5)
         host = "http://localhost:8000"

         @task
         def submit_crawl(self):
             self.client.post("/api/submit-crawl", json={"url": "http://example.com"})
     ```
   - 執行：`locust -f locustfile.py`

---

## 🔐 反爬蟲措施

- **代理管理**：`fastapi_crawler/app/proxy_manager.py` 更新 Redis 代理池。
- **User-Agent 隨機化**：使用 `fake-useragent`。
- **CAPTCHA 解決**：支援 2Captcha，需實現圖片解析。
- **擴展建議**：添加 Playwright：
  ```yaml
  playwright:
    image: mcr.microsoft.com/playwright:v1.39.0
    networks:
      - crawler_network
  ```

---

## 📂 倉庫結構

```plaintext
high_qps_crawler/
├── laravel_api/               # Laravel API 核心程式碼
│   ├── app/
│   │   ├── Http/Controllers/CrawlerController.php
│   │   ├── Grpc/CrawlerServiceClient.php
│   ├── proto/crawler.proto
│   ├── routes/api.php
│   ├── database/migrations/
│   ├── docker/
│   └── Dockerfile
├── fastapi_crawler/           # FastAPI 爬蟲核心
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
├── monitoring/                # 監控配置
│   ├── prometheus.yml
│   └── logstash.conf
├── redis_data/                # Redis 持久化
├── data_storage/              # 資料庫持久化
│   ├── mongodb_data/
│   └── postgresql_data/
└── docker-compose.yml         # Docker Compose 配置
```

---

## 🤝 貢獻指南

1. Fork 倉庫。
2. 創建分支：`git checkout -b feature/你的功能`。
3. 提交變更：`git commit -m '添加你的功能'`。
4. 推送分支：`git push origin feature/你的功能`。
5. 開啟 Pull Request。

