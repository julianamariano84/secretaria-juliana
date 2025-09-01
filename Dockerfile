FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System dependencies required by many Python packages and Playwright browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl wget ca-certificates gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpangocairo-1.0-0 libcups2 libxss1 libasound2 libxtst6 fonts-liberation libxcb1 \
 && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./

RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# If Playwright is in requirements, install browsers + any extra deps; continue if not present
RUN python -m playwright install --with-deps || true

# Copy application sources
COPY . .

ENV PORT=8000
EXPOSE 8000

# Use $PORT if provided by the host (Railway). Use sh -c so ${PORT} is expanded.
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:${PORT:-8000} app:app"]
