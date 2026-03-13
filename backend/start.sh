#!/bin/sh
set -e

# Create data directories if they don't exist
mkdir -p /app/data/chroma /app/data/pdfs/safety_alerts /app/data/pdfs/investigation_reports

# Seed database if it doesn't exist
if [ ! -f /app/data/bsee.db ]; then
    echo ">>> No database found — seeding BSEE data..."
    python -m etl.seed_data
    echo ">>> Database seeded successfully."
else
    echo ">>> Database already exists at /app/data/bsee.db"
fi

# Download and ingest PDFs if ChromaDB is empty
python -c "
import chromadb, sys
try:
    client = chromadb.PersistentClient(path='./data/chroma')
    col = client.get_or_create_collection('bsee_documents')
    if col.count() > 0:
        print(f'>>> ChromaDB already has {col.count()} chunks — skipping PDF ingestion.')
        sys.exit(0)
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" || {
    echo ">>> Downloading BSEE PDFs..."
    python -m etl.download_safety_alerts
    echo ">>> Ingesting PDFs into ChromaDB..."
    python -m etl.ingest_pdfs
    echo ">>> PDF ingestion complete."
}

# Start the API server
echo ">>> Starting Beacon GoM API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
