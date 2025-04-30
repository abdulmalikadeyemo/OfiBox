#!/bin/bash

set -e

# Colors for prettier output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Starting Hunyuan 3D API Deployment Process ===${NC}"

# Check for Gradient CLI installation
echo -e "Checking for Gradient CLI..."
if ! command -v gradient &> /dev/null; then
    echo -e "${RED}Gradient CLI not found. Installing...${NC}"
    pip install gradient
fi

# Check if API key is set
if [ -z "$PAPERSPACE_API_KEY" ]; then
    echo -e "${YELLOW}PAPERSPACE_API_KEY environment variable not set.${NC}"
    read -p "Enter your Paperspace API key: " api_key
    export PAPERSPACE_API_KEY=$api_key
fi

# Login to Gradient
echo -e "Logging in to Paperspace Gradient..."
gradient apiKey $PAPERSPACE_API_KEY

# Check for project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}PROJECT_ID environment variable not set.${NC}"
    read -p "Enter your Paperspace project ID: " project_id
    export PROJECT_ID=$project_id
fi

# Build Docker image locally first (optional)
read -p "Do you want to build the Docker image locally for testing? (y/n): " build_local
if [[ $build_local == "y" ]]; then
    echo -e "Building Docker image locally..."
    docker build -t hunyuan3d-api:latest .
    echo -e "${GREEN}Docker image built successfully.${NC}"
fi

# Validate gradient.yaml
echo -e "Validating gradient.yaml file..."
if [ ! -f "gradient.yaml" ]; then
    echo -e "${RED}Error: gradient.yaml file not found.${NC}"
    exit 1
fi

# Deploy to Paperspace Gradient
echo -e "${YELLOW}Deploying to Paperspace Gradient...${NC}"
gradient deployments create --name hunyuan3d-api --projectId $PROJECT_ID --spec gradient.yaml

echo -e "${GREEN}=== Deployment initiated successfully! ===${NC}"
echo -e "You can check the status of your deployment using:"
echo -e "${YELLOW}gradient deployments list${NC}"
echo -e "Or view logs with:"
echo -e "${YELLOW}gradient deployments logs <deployment_id>${NC}"
echo -e "${GREEN}Once deployed, the API will be available at your deployment endpoint.${NC}"
echo -e "${YELLOW}Remember to turn off your deployment when not in use to avoid unnecessary charges.${NC}" 