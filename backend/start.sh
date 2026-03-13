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

# Check if ChromaDB needs ingestion
NEEDS_INGEST=$(python -c "
import chromadb, sys
try:
    client = chromadb.PersistentClient(path='./data/chroma')
    col = client.get_or_create_collection('bsee_documents')
    if col.count() > 0:
        print(f'skip:{col.count()}')
    else:
        print('ingest')
except Exception:
    print('ingest')
" 2>/dev/null)

if echo "$NEEDS_INGEST" | grep -q "^skip"; then
    echo ">>> ChromaDB already has chunks — skipping PDF ingestion."
else
    echo ">>> Starting background PDF download and ingestion..."
    # Run download + ingestion in background so the API can start immediately
    (
        echo ">>> [Background] Downloading BSEE PDFs..."
        python -m etl.download_safety_alerts
        echo ">>> [Background] Ingesting PDFs into ChromaDB..."
        python -m etl.ingest_pdfs
        echo ">>> [Background] PDF ingestion complete."
    ) &
fi

# Start the API server immediately
echo ">>> Starting Beacon GoM API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
