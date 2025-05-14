# Use a base image with CUDA 12.1 to match PyTorch
FROM --platform=linux/amd64 pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Set CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Install build essentials and CUDA development tools needed for custom extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    cuda-toolkit-12-1 \
    && rm -rf /var/lib/apt/lists/*

# Install FastAPI and other dependencies
RUN pip install fastapi uvicorn

WORKDIR /app

COPY . /app

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install custom rasterizer extension
WORKDIR /app/hy3dgen/texgen/custom_rasterizer
RUN python3 setup.py install

# Install differentiable renderer extension
WORKDIR /app/hy3dgen/texgen/differentiable_renderer
RUN python3 setup.py install

WORKDIR /app

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "80", "--enable_tex", "--enable_t2i"]