# Build from the repository root:
#   docker build -f docker/Dockerfile -t verifyiq:latest .
FROM python:3.11-slim

# Tesseract enables the optional OCR check in code/cv/text_detector.py
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml VERSION README.md ./
COPY verifyiq/ ./verifyiq/
COPY code/ ./code/
COPY api/ ./api/
RUN pip install --no-cache-dir -e ".[v1,api]" pytesseract

COPY dataset/ ./dataset/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["verifyiq"]
CMD ["evaluate"]
