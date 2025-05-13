FROM paperspace/fastapi-deployment:latest

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && pip install -r requirements.txt

# Install custom rasterizer extension
WORKDIR /app/hy3dgen/texgen/custom_rasterizer
RUN python3 setup.py install

# Install differentiable renderer extension
WORKDIR /app/hy3dgen/texgen/differentiable_renderer
RUN python3 setup.py install

WORKDIR /app

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "80"]