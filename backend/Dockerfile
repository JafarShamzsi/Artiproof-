FROM python:3.12-slim

WORKDIR /app

# System dependencies (WeasyPrint, Cairo, PyMuPDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    libcairo2 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload directories
RUN mkdir -p uploads/pdfs uploads/annotated reports

EXPOSE 8000

# Use PORT env var (Railway sets this) or default to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
