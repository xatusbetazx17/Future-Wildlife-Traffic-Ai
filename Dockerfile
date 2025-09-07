FROM python:3.11-slim

# System deps for OpenCV video
RUN apt-get update && apt-get install -y --no-install-recommends \    ffmpeg libgl1 libglib2.0-0 \ && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.main", "--camera", "0", "--config", "data/sample_config.yaml"]