FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    TORCH_CUDA_ARCH_LIST="8.6" \
    FORCE_CUDA="1"

# Install system dependencies with optimization flags
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    ninja-build \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    curl \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install PyTorch with CUDA support optimized for A6000
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --extra-index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install the package in development mode
RUN pip3 install -e .

# Install custom rasterizer
RUN cd hy3dgen/texgen/custom_rasterizer && \
    python3 setup.py install && \
    cd ../../..

# Install differentiable renderer
RUN cd hy3dgen/texgen/differentiable_renderer && \
    python3 setup.py install && \
    cd ../../..

# Create necessary directories with proper permissions
RUN mkdir -p models gradio_cache && \
    chmod -R 777 models gradio_cache

# Expose the ports the app runs on
EXPOSE 8000

# Set up healthcheck for better container management
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application with optimized performance
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] 