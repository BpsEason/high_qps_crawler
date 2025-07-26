import grpc
from concurrent import futures
import asyncio
import os

from proto import crawler_pb2
from proto import crawler_pb2_grpc
from app.crawler import perform_crawl
from celery_workers.celery_app import app as celery_app # Import Celery app

class CrawlerServicer(crawler_pb2_grpc.CrawlerServiceServicer):
    async def Crawl(self, request, context):
        print(f"Received gRPC crawl request for URL: {request.url}, Task ID: {request.task_id}")
        try:
            # 1. Perform the actual web crawl using the FastAPI core
            content = await perform_crawl(request.url, request.task_id) # Pass task_id to crawler
            
            # 2. Dispatch the result to Celery for asynchronous storage
            # This ensures FastAPI quickly frees up resources and Celery handles the DB write.
            celery_app.send_task(
                'tasks.store_data', 
                args=[request.url, content, request.task_id], # Pass task_id to Celery
                kwargs={}
            )
            print(f"Dispatched URL {request.url} (Task ID: {request.task_id}) to Celery for storage.")

            return crawler_pb2.CrawlResponse(status="SUCCESS", content="Crawled content dispatched for storage.")
        except Exception as e:
            print(f"Crawl failed for {request.url} (Task ID: {request.task_id}): {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            # Also dispatch a Celery task to update status as FAILED
            celery_app.send_task(
                'tasks.update_task_status_failed',
                args=[request.task_id, str(e)],
                kwargs={}
            )
            return crawler_pb2.CrawlResponse(status="FAILED", error=str(e))

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=os.cpu_count() * 2))
    crawler_pb2_grpc.add_CrawlerServiceServicer_to_server(CrawlerServicer(), server)
    server.add_insecure_port('[::]:50051')
    print("FastAPI gRPC Server starting on port 50051...")
    await server.start()
    await server.wait_for_termination()

