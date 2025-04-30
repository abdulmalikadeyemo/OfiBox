#!/bin/bash

# Colors for prettier output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for Gradient CLI installation
if ! command -v gradient &> /dev/null; then
    echo -e "${RED}Gradient CLI not found. Installing...${NC}"
    pip install gradient
fi

# Check if API key is set
if [ -z "$PAPERSPACE_API_KEY" ]; then
    echo -e "${YELLOW}PAPERSPACE_API_KEY environment variable not set.${NC}"
    read -p "Enter your Paperspace API key: " api_key
    export PAPERSPACE_API_KEY=$api_key
    gradient apiKey $api_key
fi

# Function to check component installation in a deployment
check_component_installation() {
    local DEPLOYMENT_ID=$1
    echo -e "${BLUE}=== Checking Hunyuan Components Installation ===${NC}"
    
    # Create a temporary script to check component installation
    cat > check_components.py << 'EOF'
import sys
try:
    # Try importing the custom rasterizer
    from hy3dgen.texgen.custom_rasterizer import rasterizer
    print("✅ Custom rasterizer is properly installed")
except ImportError:
    print("❌ Custom rasterizer is NOT properly installed")
    
try:
    # Try importing the differentiable renderer
    from hy3dgen.texgen.differentiable_renderer import renderer
    print("✅ Differentiable renderer is properly installed")
except ImportError:
    print("❌ Differentiable renderer is NOT properly installed")

# Check CUDA availability
try:
    import torch
    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        print(f"✅ CUDA is available with {device_count} device(s)")
        print(f"   Current device: {current_device} ({device_name})")
    else:
        print("❌ CUDA is NOT available")
except Exception as e:
    print(f"❌ Error checking CUDA: {e}")
EOF

    # Execute the script in the deployment
    echo -e "${YELLOW}Executing component check in deployment...${NC}"
    gradient deployments run $DEPLOYMENT_ID \
        --command "python3 check_components.py" \
        --wait
    
    # Clean up
    rm check_components.py
}

# List all deployments
echo -e "${BLUE}=== Fetching deployment list... ===${NC}"
DEPLOYMENTS=$(gradient deployments list --json)

# Check if there are any deployments
if [ -z "$DEPLOYMENTS" ] || [ "$DEPLOYMENTS" == "[]" ]; then
    echo -e "${RED}No deployments found.${NC}"
    exit 1
fi

# Parse deployment info
echo -e "${BLUE}=== Your Deployments ===${NC}"
echo "$DEPLOYMENTS" | python3 -c "
import sys, json
deployments = json.load(sys.stdin)
for i, d in enumerate(deployments):
    status_color = '\033[32m' if d.get('status') == 'Running' else '\033[31m'
    print(f\"{i+1}. \033[1m{d.get('name')}\033[0m (ID: {d.get('id')})\"
          f\" - Status: {status_color}{d.get('status')}\033[0m\"
          f\" - Endpoint: {d.get('endpoint', 'N/A')}\")
"

# Ask which deployment to monitor
echo -e "${YELLOW}Which deployment would you like to monitor?${NC}"
read -p "Enter the deployment number: " deployment_num

# Validate input
if ! [[ "$deployment_num" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Invalid input. Please enter a number.${NC}"
    exit 1
fi

# Get the selected deployment ID
DEPLOYMENT_ID=$(echo "$DEPLOYMENTS" | python3 -c "
import sys, json
deployments = json.load(sys.stdin)
try:
    print(deployments[int('$deployment_num')-1]['id'])
except (IndexError, ValueError):
    print('')
")

if [ -z "$DEPLOYMENT_ID" ]; then
    echo -e "${RED}Invalid deployment number.${NC}"
    exit 1
fi

# Monitor options
echo -e "${BLUE}=== Monitoring Options for Deployment: $DEPLOYMENT_ID ===${NC}"
echo -e "1. View logs"
echo -e "2. Check metrics (if available)"
echo -e "3. Check deployment status"
echo -e "4. Scale deployment"
echo -e "5. Check component installation"
echo -e "6. Exit"

read -p "Choose an option: " option

case $option in
    1)
        echo -e "${BLUE}=== Fetching logs... ===${NC}"
        gradient deployments logs $DEPLOYMENT_ID --follow
        ;;
    2)
        echo -e "${BLUE}=== Fetching metrics (if available)... ===${NC}"
        # Getting endpoint URL to check metrics
        ENDPOINT=$(echo "$DEPLOYMENTS" | python3 -c "
        import sys, json
        deployments = json.load(sys.stdin)
        try:
            print(deployments[int('$deployment_num')-1]['endpoint'])
        except (IndexError, ValueError, KeyError):
            print('')
        ")
        
        if [ -z "$ENDPOINT" ]; then
            echo -e "${RED}Endpoint not available.${NC}"
        else
            echo -e "${GREEN}Metrics should be available at: ${ENDPOINT}/metrics${NC}"
            echo -e "${YELLOW}Attempting to fetch metrics...${NC}"
            curl -s "${ENDPOINT}/metrics" || echo -e "${RED}Failed to fetch metrics.${NC}"
        fi
        ;;
    3)
        echo -e "${BLUE}=== Checking deployment status... ===${NC}"
        gradient deployments get $DEPLOYMENT_ID
        ;;
    4)
        echo -e "${BLUE}=== Scale deployment ===${NC}"
        read -p "Enter the number of replicas (0 to stop the deployment): " replicas
        if [[ "$replicas" =~ ^[0-9]+$ ]]; then
            gradient deployments update $DEPLOYMENT_ID --replicas $replicas
            echo -e "${GREEN}Deployment scaled to $replicas replicas.${NC}"
        else
            echo -e "${RED}Invalid input. Please enter a number.${NC}"
        fi
        ;;
    5)
        check_component_installation $DEPLOYMENT_ID
        ;;
    6)
        echo -e "${GREEN}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option.${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}=== Monitoring completed ===${NC}" 