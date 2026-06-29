# syntax=docker/dockerfile:1
# NOTE: build with the PROJECT ROOT as context so /data can be copied in:
#   docker build -f backend/Dockerfile -t northwind-api .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install deps first for layer caching.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the local embedding model into the image so the first-boot ingest
# works offline and starts instantly (no runtime model fetch from HuggingFace).
# Keep this model id in sync with EMBEDDING_MODEL in config.py / .env.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# App code + entrypoint.
COPY backend/app ./app
COPY backend/entrypoint.sh .
RUN chmod +x entrypoint.sh

# Dataset is baked into the image so the container is self-sufficient.
COPY data /data

EXPOSE 8000
CMD ["./entrypoint.sh"]
