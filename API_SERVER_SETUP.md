# Hunyuan3D API Server Setup Guide

This guide provides instructions for setting up and running the Hunyuan3D API server in a cloud environment.

## System Requirements

- CUDA-compatible GPU with at least 16GB VRAM (24GB+ recommended)
- 16GB+ RAM
- 20GB+ free disk space
- Ubuntu 20.04+ or similar Linux distribution
- Python 3.9+

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Tencent/Hunyuan3D.git
cd Hunyuan3D
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -e .
pip install -r requirements.txt
```

### 4. Download the Models

Run the download script to fetch all required models automatically:

```bash
python download_models.py
```

The models will be downloaded to the appropriate folders automatically.

> **Note:** If you prefer to download the models manually, you can get them from the following sources and place them in the appropriate folders:
> - Shape Generation model: `models/hunyuan3d-shape-v1-0`
> - Texture Generation model: `models/hunyuan3d-paint-v2-0`

### 5. Configure Environment Variables

If needed, you can configure the following environment variables:

```bash
export CUDA_VISIBLE_DEVICES=0  # Specify which GPU to use
export HF_HOME=/path/to/cache  # Custom Hugging Face cache directory
```

## Running the API Server

### Basic Command

```bash
python api_server.py --host 0.0.0.0 --port 8081
```

### Options for Different Configurations

#### Shape Generation Only

If you want to run only the shape generation service:

```bash
python api_server.py --host 0.0.0.0 --port 8081 --disable_texgen
```

#### Enable Texture Generation

To explicitly enable texture generation:

```bash
python api_server.py --host 0.0.0.0 --port 8081 --enable_tex
```

#### Texture Generation on CPU (for memory-limited systems)

If you're experiencing CUDA out-of-memory errors when generating textures:

```bash
python api_server.py --host 0.0.0.0 --port 8081 --texgen_device cpu
```

#### Memory-Optimized Mode

For systems with limited VRAM:

```bash
python api_server.py --host 0.0.0.0 --port 8081 --low_vram_mode
```

## API Usage Examples

### Text-to-3D Shape Generation

Send a POST request to the `/generate` endpoint:

```bash
curl -X POST http://localhost:8081/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a small teddy bear",
    "negative_prompt": "broken, poor quality",
    "num_inference_steps": 30,
    "guidance_scale": 7.5
  }'
```

### Texture Generation for 3D Model

Send a POST request to the `/generate` endpoint with texture generation enabled:

```bash
curl -X POST http://localhost:8081/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a small teddy bear made of brown fabric",
    "negative_prompt": "broken, poor quality",
    "num_inference_steps": 30,
    "guidance_scale": 7.5,
    "gen_texture": true,
    "texture_prompt": "fuzzy brown fabric with black button eyes"
  }'
```

### Text-to-Image Generation

Send a POST request to the `/text2img` endpoint:

```bash
curl -X POST http://localhost:8081/text2img \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cute teddy bear",
    "seed": 42
  }'
```

### Image-to-Texture Generation

Send a POST request to the `/img2texture` endpoint with a mesh file and a reference image:

```bash
curl -X POST http://localhost:8081/img2texture \
  -F "mesh=@/path/to/your/mesh.obj" \
  -F "image=@/path/to/your/reference.png"
```

## Troubleshooting

### CUDA Out of Memory

If you encounter CUDA out of memory errors during texture generation:

1. Use the `--texgen_device cpu` option to offload texture generation to CPU
2. Use the `--low_vram_mode` option for memory optimization
3. Reduce batch sizes or model precision if available

### Connection Issues

If clients cannot connect to your server:

1. Ensure the correct host and port are specified
2. Check that your firewall/security groups allow the specified port
3. Verify the server is running and listening on the expected interface

### Common Errors

- **Model loading failures**: Verify that all models were correctly downloaded
- **ImportError**: Ensure all dependencies are properly installed
- **Permission errors**: Check file permissions in the models directory

## Cloud-Specific Setup

### AWS

For AWS EC2 instances:
- Use g4dn.xlarge or larger with the Deep Learning AMI
- Configure security groups to allow inbound traffic on your API port

### Google Cloud Platform

For GCP instances:
- Use n1-standard-8 with NVIDIA T4 or better
- Use the Deep Learning VM images with PyTorch pre-installed

### Azure

For Azure instances:
- Use NC series VMs with GPU support
- Configure NSG rules to allow inbound traffic on your API port

## Health Monitoring

The API server provides a health endpoint that can be used to monitor its status:

```bash
curl http://localhost:8081/health
```

This should return a 200 OK response if the server is running correctly. 