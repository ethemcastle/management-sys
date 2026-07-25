FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Tables + seed load on startup via the app lifespan.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
