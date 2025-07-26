FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate gRPC stubs from the proto file
RUN python3 -m grpc_tools.protoc -I./proto --python_out=. --pyi_out=. --grpc_python_out=. ./proto/crawler.proto

EXPOSE 8000 # FastAPI HTTP port for health/metrics
EXPOSE 50051 # gRPC port

# CMD is now managed by docker-compose.yml for consistency and flexibility.
