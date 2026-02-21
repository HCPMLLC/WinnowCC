FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for local file storage (uploads, generated docs)
RUN mkdir -p /app/data/uploads /app/generated

# Expose port
EXPOSE 8080

# Cloud Run uses PORT env var (default 8080)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
