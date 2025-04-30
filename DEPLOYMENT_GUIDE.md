# Hunyuan 3D API Deployment Guide for Paperspace A6000

This guide provides detailed instructions for deploying the Hunyuan 3D API on Paperspace using A6000 GPUs for optimal performance and scalability.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Scaling](#scaling)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Advanced Monitoring](#advanced-monitoring)
- [Integrating External Services](#integrating-external-services)

## Prerequisites

Before deploying the Hunyuan 3D API, ensure you have:

1. A Paperspace account with access to A6000 GPUs
2. Paperspace API key (available from your Paperspace account settings)
3. Gradient CLI installed (`pip install gradient`)
4. Docker installed locally (optional, for testing)
5. Git to clone this repository

## Setup

### 1. Create a Project on Paperspace

If you don't already have a project:

1. Log in to your Paperspace account at https://console.paperspace.com/
2. Navigate to the Gradient section
3. Click "Create Project" and give it a name
4. Save the Project ID, which will be needed during deployment

### 2. Clone the Repository

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/Hunyuan3D.git
cd Hunyuan3D
```

### 3. Prepare the Environment

1. Set your Paperspace API key:
   ```bash
   export PAPERSPACE_API_KEY=<your-api-key>
   export PROJECT_ID=<your-project-id>
   ```

2. Make the deployment and monitoring scripts executable:
   ```bash
   chmod +x deploy.sh monitor.sh
   ```

3. Install required dependencies:
   ```bash
   # Install Gradient CLI if not already installed
   pip install gradient
   
   # Install Docker if not already installed (optional, for local testing)
   # For Ubuntu:
   # sudo apt-get update && sudo apt-get install docker.io
   # sudo systemctl enable --now docker
   
   # For macOS:
   # brew install docker
   ```

### 4. Implement Metrics Middleware (Optional)

If you want to enable the Prometheus metrics for monitoring:

1. Ensure the `metrics_middleware.py` file is in your project root
2. Modify your `api_server.py` to implement the middleware:

   ```python
   from fastapi import FastAPI
   from metrics_middleware import metrics_middleware

   app = FastAPI()
   
   # Initialize metrics middleware
   metrics_middleware(app)
   
   # Rest of your FastAPI application code...
   ```

3. The metrics will be available at the `/metrics` endpoint once deployed

## Deployment

The deployment uses a fully optimized Docker container with the following key features:

- **CUDA 12.1** optimized for the A6000 GPU architecture
- **PyTorch 2.1.0** with CUDA support
- **Multi-worker** configuration for improved request handling
- **Health checks** for enhanced stability
- **Auto-scaling** based on GPU and CPU utilization

### Hunyuan-Specific Components

The deployment handles the special installation requirements for Hunyuan 3D API, including:

1. **Custom Rasterizer Installation**: 
   The custom rasterizer module from `hy3dgen/texgen/custom_rasterizer` is automatically built and installed during container creation.

2. **Differentiable Renderer Installation**:
   The differentiable renderer from `hy3dgen/texgen/differentiable_renderer` is also built and installed during deployment.

3. **Package Installation in Development Mode**:
   The package is installed in development mode with `pip install -e .` to ensure proper module imports.

These steps are automatically handled in the Dockerfile, so you don't need to manually run these installations.

### Deployment Options

#### 1. Using the Deployment Script

The easiest way to deploy is using our automated script:

```bash
./deploy.sh
```

The script will:
- Check for required prerequisites
- Validate your configuration
- Optionally build the Docker image locally for testing
- Deploy to Paperspace using the gradient.yaml configuration

#### 2. Manual Deployment

If you prefer to deploy manually:

```bash
# Login to Gradient
gradient apiKey <your-api-key>

# Deploy using the specification file
gradient deployments create --name hunyuan3d-api --projectId <your-project-id> --spec gradient.yaml
```

### Configuration Details

The `gradient.yaml` file contains the following key configurations:

- **A6000 GPU** instance type for optimal performance
- **16GB shared memory** for improved model loading
- **100GB persistent storage** for models and cache
- **Auto-scaling** from 1 to 4 instances based on load
- **Health checks** for improved reliability

## Monitoring

You can monitor your deployment using the provided monitoring script:

```bash
./monitor.sh
```

This script allows you to:
- View deployment logs in real-time
- Check performance metrics
- Monitor deployment status
- Scale the number of replicas up or down

### Manual Monitoring

To manually check your deployment:

```bash
# List all deployments
gradient deployments list

# View logs for a specific deployment
gradient deployments logs <deployment-id>

# Get deployment details
gradient deployments get <deployment-id>
```

## Scaling

The deployment is configured to auto-scale based on:
- CPU utilization (target: 70%)
- GPU utilization (target: 80%)

### Manual Scaling

You can manually adjust the number of replicas:

```bash
# Scale to a specific number of replicas
gradient deployments update <deployment-id> --replicas <number>

# Stop the deployment (without deleting it)
gradient deployments update <deployment-id> --replicas 0
```

## Performance Optimization

The Hunyuan 3D API deployment includes several optimizations for A6000 GPUs:

1. **CUDA Architecture Optimization**: Set to CUDA capability 8.6 for A6000
2. **Batch Processing**: Configured to process multiple requests efficiently
3. **Memory Management**: Optimized shared memory and GPU memory utilization
4. **Multi-worker Configuration**: Utilizes multiple worker processes for parallel processing

### Environment Variables

Fine-tune performance via environment variables in `gradient.yaml`:

- `HUNYUAN3D_BATCH_SIZE`: Adjust batch size for inference (default: 4)
- `HUNYUAN3D_NUM_WORKERS`: Number of worker threads (default: 4)
- `HUNYUAN3D_CUDA_OPTIMIZATION`: Enable extra CUDA optimizations (default: true)

## Troubleshooting

### Common Issues

1. **Deployment Fails to Start**:
   - Check if the A6000 GPU is available in your region
   - Verify that your account has access to A6000 instances
   - Check the deployment logs for specific errors

2. **Out of Memory Errors**:
   - Reduce the batch size via `HUNYUAN3D_BATCH_SIZE` environment variable
   - Consider using the `--low-memory` flag for model loading

3. **Slow Performance**:
   - Verify that CUDA optimizations are enabled
   - Ensure there aren't other workloads competing for GPU resources
   - Check if auto-scaling is working properly

### Getting Support

If you encounter issues not covered in this guide:

1. Check the API server logs: `gradient deployments logs <deployment-id>`
2. Review the Paperspace documentation for deployment troubleshooting
3. Contact Paperspace support with your deployment ID and error details

## Cost Management

Remember that running A6000 GPU instances incurs costs. To minimize expenses:

1. Scale down to 0 replicas when not in use
2. Monitor usage patterns and adjust auto-scaling parameters accordingly
3. Consider using scheduled deployments for predictable workloads

## Security Considerations

1. The deployment uses HTTPS by default for all endpoints
2. API keys and sensitive data should be managed through environment variables
3. Consider implementing additional authentication for production deployments

## Advanced Monitoring

### Setting Up a Monitoring Dashboard

Once your deployment is running with metrics enabled, you can set up a comprehensive monitoring dashboard:

1. **Prometheus Integration**:
   
   You can deploy a Prometheus server to scrape metrics from your API endpoint:

   ```yaml
   # prometheus.yml
   global:
     scrape_interval: 15s
   
   scrape_configs:
     - job_name: 'hunyuan3d-api'
       scheme: https
       static_configs:
         - targets: ['your-deployment-endpoint.paperspace.io']
       metrics_path: /metrics
   ```

2. **Grafana Dashboard**:

   Create a Grafana dashboard to visualize your metrics. Here's a sample dashboard configuration:

   ```bash
   # Create a new dashboard with these panels:
   
   # Panel 1: API Request Rate
   # Query: rate(http_requests_total[1m])
   
   # Panel 2: GPU Memory Usage
   # Query: gpu_memory_usage_bytes
   
   # Panel 3: Model Inference Latency
   # Query: histogram_quantile(0.95, sum(rate(model_inference_duration_seconds_bucket[5m])) by (le, model_type))
   
   # Panel 4: Active Requests
   # Query: sum(http_active_requests) by (endpoint)
   ```

3. **Paperspace Metrics Integration**:

   Paperspace Gradient also provides built-in metrics that can be accessed from the Deployments tab:
   
   - Navigate to your project in Paperspace console
   - Select the deployment
   - Click on the "Metrics" tab to view CPU, memory, and GPU utilization

### Monitoring Best Practices

1. **Alert Setup**:
   
   Set up alerts for critical metrics:
   
   - High GPU memory usage (>90%)
   - High error rates (>1%)
   - Slow response times (>2s)

2. **Log Aggregation**:
   
   Consider using a log aggregation tool like ELK Stack or Loki to collect and analyze logs:
   
   ```bash
   # Example Loki configuration for Docker
   docker run -d --name loki -p 3100:3100 grafana/loki:latest
   
   # Configure Promtail to ship logs
   docker run -d --name promtail -v /var/log:/var/log grafana/promtail:latest
   ```

3. **Regular Health Checks**:
   
   Implement a scheduled task to periodically check your deployment health:
   
   ```bash
   # Add to your crontab
   */30 * * * * curl -f https://your-deployment-endpoint.paperspace.io/health || notify-admin.sh
   ```

## Integrating External Services

### Connecting to Model Repositories

The Hunyuan 3D API can load models from various sources. Here's how to configure it:

1. **Loading from Hugging Face**:

   To use models from Hugging Face Model Hub, add these environment variables to your `gradient.yaml`:

   ```yaml
   env:
     - name: HF_API_TOKEN
       value: "your-huggingface-token"
     - name: MODEL_SOURCE
       value: "huggingface"
     - name: MODEL_ID
       value: "tencent/Hunyuan3D-2mini"
   ```

2. **Loading from S3**:

   To load models from an S3 bucket:

   ```yaml
   env:
     - name: AWS_ACCESS_KEY_ID
       value: "your-access-key"
     - name: AWS_SECRET_ACCESS_KEY
       value: "your-secret-key"
     - name: MODEL_SOURCE
       value: "s3"
     - name: S3_BUCKET
       value: "your-models-bucket"
     - name: S3_MODEL_PATH
       value: "path/to/model"
   ```

3. **Using Paperspace Model Registry**:

   To use the Paperspace Model Registry:

   ```yaml
   env:
     - name: MODEL_SOURCE
       value: "paperspace"
     - name: PAPERSPACE_MODEL_ID
       value: "your-model-id"
   ```

### Connecting to External APIs

If your API needs to communicate with external services:

1. **Add necessary environment variables**:

   ```yaml
   env:
     - name: EXTERNAL_API_ENDPOINT
       value: "https://api.example.com"
     - name: EXTERNAL_API_KEY
       value: "your-api-key"
   ```

2. **Configure network access**:

   Ensure your deployment has proper network access to external services. Paperspace deployments have internet access by default, but you may need to configure specific firewall rules for some services.

3. **Handling credentials securely**:

   For production deployments, use Paperspace Secrets instead of embedding credentials directly:

   ```yaml
   secrets:
     - name: AWS_SECRET_ACCESS_KEY
       key: aws-secret-key
     - name: HF_API_TOKEN
       key: huggingface-token
   ```

   Create these secrets in the Paperspace console under your project settings. 