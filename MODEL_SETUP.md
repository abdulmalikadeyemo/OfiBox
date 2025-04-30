# Hunyuan3D-2 Model Setup Guide

This guide explains how to set up the models required for Hunyuan3D-2 API server.

## Model Requirements

Hunyuan3D-2 requires the following models:

1. **Shape Generation Model**: Used for generating 3D shapes from images
   - Default: `tencent/Hunyuan3D-2mini` (smaller model, faster generation)
   - Alternative: `tencent/Hunyuan3D-2` (larger model, better quality)

2. **Texture Model**: Used for applying textures to 3D shapes
   - Default: `tencent/Hunyuan3D-2`

3. **Text-to-Image Model** (optional): Used for generating images from text
   - Default: `Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled`

## Model Setup Options

You have two options for setting up the models:

### Option 1: Download Models Ahead of Time (Recommended)

We provide a script to download the models ahead of time. This is useful if you have a stable internet connection and want to ensure the models are available locally.

```bash
# Download all models to the default directory (./models)
python download_models.py

# Specify an alternate directory
python download_models.py --models_dir /path/to/models

# Download only specific models
python download_models.py --shape_model tencent/Hunyuan3D-2mini --texture_model tencent/Hunyuan3D-2
```

### Option 2: Let the API Server Download Models On-Demand

The API server will attempt to download models automatically if they are not found locally.

```bash
# Run the API server with default model paths
python api_server.py

# Specify local model paths
python api_server.py --model_path /path/to/models/Hunyuan3D-2mini --tex_model_path /path/to/models/Hunyuan3D-2

# Enable text-to-image and texture features
python api_server.py --enable_tex --enable_t2i
```

## Troubleshooting Model Loading Issues

If you encounter issues loading models:

1. **Check Internet Connection**: Ensure you have a stable internet connection when downloading models.

2. **Check Disk Space**: Make sure you have enough disk space for the models (several GB).

3. **Check Model Paths**: Verify the model paths are correct and the directories exist.

4. **Check Model Directory Permissions**: Ensure the model directory is writable.

5. **Manually Download**: If automatic downloads fail, you can manually download the models from Hugging Face:
   - Visit the model page on Hugging Face (e.g., [tencent/Hunyuan3D-2mini](https://huggingface.co/tencent/Hunyuan3D-2mini))
   - Download the model files
   - Place them in the appropriate directory structure

## Example Directory Structure

When downloading models, they will be organized as follows:

```
models/
├── Hunyuan3D-2mini/
│   ├── hunyuan3d-dit-v2-mini-turbo/
│   │   ├── config.json
│   │   ├── model_index.json
│   │   └── ...
├── Hunyuan3D-2/
│   └── ...
└── HunyuanDiT-v1.1-Diffusers-Distilled/
    └── ...
```

## Additional Options

For additional configuration options, run:

```bash
python api_server.py --help
python download_models.py --help
``` 