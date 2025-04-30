"""
Prometheus metrics middleware for the Hunyuan 3D API server.
This module adds Prometheus metrics tracking to the FastAPI application.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest

# Define metrics
REQUEST_COUNT = Counter(
    "http_requests_total", 
    "Total count of HTTP requests", 
    ["method", "endpoint", "status_code"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", 
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)
ACTIVE_REQUESTS = Gauge(
    "http_active_requests", 
    "Number of active HTTP requests",
    ["method", "endpoint"]
)
GPU_MEMORY_USAGE = Gauge(
    "gpu_memory_usage_bytes", 
    "GPU memory usage in bytes",
    ["device"]
)
MODEL_INFERENCE_COUNT = Counter(
    "model_inference_total", 
    "Total number of model inferences",
    ["model_type"]
)
MODEL_INFERENCE_LATENCY = Histogram(
    "model_inference_duration_seconds", 
    "Model inference latency in seconds",
    ["model_type"]
)

def get_gpu_memory_usage():
    """Get GPU memory usage."""
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                memory_allocated = torch.cuda.memory_allocated(i)
                GPU_MEMORY_USAGE.labels(device=f"cuda:{i}").set(memory_allocated)
    except (ImportError, Exception):
        pass

def metrics_middleware(app: FastAPI) -> None:
    """Add Prometheus metrics middleware to the FastAPI application."""
    
    @app.middleware("http")
    async def add_metrics(request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path
        
        # Skip metrics endpoint to avoid recursion
        if path == "/metrics":
            return await call_next(request)
        
        # Track active requests
        ACTIVE_REQUESTS.labels(method=method, endpoint=path).inc()
        
        # Track request latency
        start_time = time.time()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            # Record request latency
            latency = time.time() - start_time
            REQUEST_LATENCY.labels(method=method, endpoint=path).observe(latency)
            
            # Record request count
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
            
            # Decrement active requests
            ACTIVE_REQUESTS.labels(method=method, endpoint=path).dec()
            
            # Update GPU memory usage
            get_gpu_memory_usage()
        
        return response
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        # Update GPU memory usage before returning metrics
        get_gpu_memory_usage()
        return Response(
            content=generate_latest(),
            media_type="text/plain"
        )

def track_inference(model_type: str):
    """Decorator to track model inference time."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Track inference count
            MODEL_INFERENCE_COUNT.labels(model_type=model_type).inc()
            
            # Track inference latency
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency = time.time() - start_time
                MODEL_INFERENCE_LATENCY.labels(model_type=model_type).observe(latency)
        
        return wrapper
    return decorator 