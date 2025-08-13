FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything including static/
COPY . .

# Cloud Run will set $PORT, so we bind to it
ENV PORT=8080

CMD ["python", "server.py"]
