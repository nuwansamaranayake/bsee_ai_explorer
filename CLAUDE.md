# Beacon GoM — CLAUDE.md

> AI Safety & Regulatory Intelligence for Offshore Operations

## Project Identity

- **Product Name:** Beacon GoM
- **Repository:** bsee-ai-explorer
- **Tagline:** AI Safety & Regulatory Intelligence for Offshore Operations
- **Live URL:** gomsafety.aigniteconsulting.ai
- **Developer:** Dinidu Samaranayake (CS, Texas A&M University)
- **Supervised by:** Nuwan Samaranayake — AiGNITE Consulting

## What This Project Does

Beacon GoM is a full-stack, AI-powered safety analytics platform built on public BSEE (Bureau of Safety and Environmental Enforcement) data covering every operator in the Gulf of Mexico. It transforms raw government data into actionable intelligence through interactive dashboards, AI trend analysis, natural language Q&A, document intelligence (RAG), and automated regulatory monitoring.

Think of it as a Bloomberg Terminal for Gulf of Mexico safety data, powered by AI.

## Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| React 18+ | Functional components with hooks |
| Vite | Build tooling, dev server |
| TailwindCSS | Utility-first styling |
| shadcn/ui | Component library (Radix-based) |
| Recharts | Interactive charting |
| TanStack Query | Server state management + caching |
| React Router | Page routing |

### Backend
| Technology | Purpose |
|---|---|
| FastAPI | Python API framework (async, OpenAPI auto-docs) |
| SQLite | Structured BSEE data storage |
| ChromaDB | Vector DB for RAG document search |
| Claude API (Sonnet) | AI trend analysis, Q&A, categorization |
| LangChain | RAG pipeline (chunking, embedding, retrieval) |
| PyMuPDF (fitz) | PDF text extraction |
| Pandas | ETL data cleaning/loading |

### Infrastructure
| Component | Details |
|---|---|
| Docker + Compose | Containerized frontend, backend, nginx |
| Nginx | Reverse proxy, SSL termination |
| Certbot | Let's Encrypt SSL auto-renewal |
| Hostinger VPS | Production host (Ubuntu 22.04) |

## Project Structure

bsee-ai-explorer/
├── docker-compose.yml
├── docker-compose.prod.yml
├── nginx.conf
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Compliance.tsx
│       │   ├── Chat.tsx
│       │   ├── Documents.tsx
│       │   └── Reports.tsx
│       ├── components/
│       │   ├── AppSidebar.tsx
│       │   ├── ChartCard.tsx
│       │   ├── MetricCard.tsx
│       │   ├── OperatorSelector.tsx
│       │   ├── FilterPanel.tsx
│       │   ├── ChatInterface.tsx
│       │   └── CitationCard.tsx
│       ├── hooks/
│       │   ├── useOperators.ts
│       │   └── useIncidents.ts
│       └── lib/
│           └── api.ts
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── operators.py
│   │   ├── incidents.py
│   │   ├── incs.py
│   │   ├── platforms.py
│   │   ├── production.py
│   │   ├── analyze.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── reports.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── claude_service.py
│   │   ├── rag_service.py
│   │   ├── sql_service.py
│   │   └── report_service.py
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── download_bsee.py
│   │   ├── clean_incidents.py
│   │   ├── load_database.py
│   │   ├── ingest_pdfs.py
│   │   └── validate_bsee_access.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   └── database.py
│   └── data/
│       ├── .gitkeep
│       ├── chroma/
│       └── pdfs/
├── deploy/
│   ├── setup-vps.sh
│   └── setup-ssl.sh
└── docs/

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/operators | List all GoM operators with counts |
| GET | /api/incidents | Filtered incident data with pagination |
| GET | /api/incs | Filtered violation data |
| GET | /api/platforms | Platform data with INC counts |
| GET | /api/production | Production volumes for normalization |
| POST | /api/analyze/trends | AI trend analysis from filter state |
| POST | /api/analyze/categorize | AI root cause categorization |
| POST | /api/chat | Natural language Q&A (text-to-SQL) |
| POST | /api/documents/search | RAG search with citations |
| GET | /api/reports/generate | PDF briefing download |
| GET | /health | Health check endpoint |

## Coding Conventions

- **TypeScript** for all frontend code (strict mode)
- **Python 3.11+** with type hints for all backend code
- **Pydantic v2** for request/response schemas
- **Functional React components** with hooks only (no class components)
- **TanStack Query** for all API calls (no raw fetch/axios in components)
- **shadcn/ui** for all interactive UI elements
- **snake_case** for Python, **camelCase** for TypeScript
- **Async/await** for all FastAPI endpoints
- All API responses follow `{ data: T, meta?: {} }` envelope pattern
- Error responses: `{ error: string, detail?: string, status: number }`

## Environment Variables

```env
# Backend (.env)
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_PATH=./data/bsee.db
CHROMA_PATH=./data/chroma
PDF_PATH=./data/pdfs
CLAUDE_MODEL=claude-sonnet-4-5-20250514
LOG_LEVEL=INFO

# Frontend (.env)
VITE_API_URL=http://localhost:8000
```

## Important Notes for Claude Code

- Always check BSEE column names against the data dictionary — they use ALL_CAPS with underscores
- Operator names have variations (e.g., "WOODSIDE ENERGY" vs "WOODSIDE PETROLEUM") — always use the operator mapping table
- BSEE dates come in various formats (MM/DD/YYYY, YYYY-MM-DD) — normalize to ISO 8601
- Production data uses BOE (Barrels of Oil Equivalent) for normalization
- All AI responses MUST cite their data source (table/query or document/page)
- Frontend must handle loading, error, and empty states for every API call
- Never expose the ANTHROPIC_API_KEY to the frontend — all AI calls go through the backend
