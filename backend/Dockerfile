FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data directories and startup script are ready
RUN mkdir -p /app/data/chroma /app/data/pdfs && chmod +x /app/start.sh

EXPOSE 8000

# Startup script seeds DB if missing, then launches uvicorn
CMD ["/app/start.sh"]
