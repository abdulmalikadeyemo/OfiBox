# Use a base image with CUDA 12.6 to match PyTorch
FROM --platform=linux/amd64 pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

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