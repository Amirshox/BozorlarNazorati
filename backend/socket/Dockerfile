# Use an official Python runtime as the relative image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libglib2.0-0 libsm6 libxrender1 libxext6 libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . /app

# Specify the command to run on container start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
