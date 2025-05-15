# Use official Python 3.11 image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ninja-build \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire repository content
COPY . .

# Install Python packages from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=8080

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["python", "gradio_app.py", "--host", "0.0.0.0", "--port", "8080"]