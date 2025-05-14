# Use a base image with CUDA 12.1 to match PyTorch
FROM --platform=linux/amd64 pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Set CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Add NVIDIA repository and install CUDA toolkit
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.0-1_all.deb && \
    dpkg -i cuda-keyring_1.0-1_all.deb && \
    apt-get update && \
    apt-get install -y cuda-toolkit-12-1 && \
    rm -rf /var/lib/apt/lists/* && \
    rm cuda-keyring_1.0-1_all.deb

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