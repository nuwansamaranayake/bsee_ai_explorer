from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="Beacon GoM API",
    description="AI Safety & Regulatory Intelligence for Offshore Operations",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev
        "http://localhost:3000",
        "http://localhost",
        "https://gomsafety.aigniteconsulting.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from routers import operators, incidents, incs, platforms, production, analyze, chat, documents, reports

app.include_router(operators.router, prefix="/api", tags=["operators"])
app.include_router(incidents.router, prefix="/api", tags=["incidents"])
app.include_router(incs.router, prefix="/api", tags=["incs"])
app.include_router(platforms.router, prefix="/api", tags=["platforms"])
app.include_router(production.router, prefix="/api", tags=["production"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(reports.router, prefix="/api", tags=["reports"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "beacon-gom-api", "version": "0.1.0"}
