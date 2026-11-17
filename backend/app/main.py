from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from backend.app.config import settings
from backend.app.database import init_db, get_connection
from backend.app.seed import seed_database
from backend.app.routes.public import router as public_router
from backend.app.routes.internal import router as internal_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização: verificar se banco existe e possui dados
    init_db(drop_existing=False)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM orders")
    count = cursor.fetchone()["cnt"]
    conn.close()

    if count == 0:
        print("[Nex] Banco de dados vazio. Executando seed determinístico inicial...")
        seed_database(drop_existing=True)
    else:
        print(f"[Nex] Banco de dados pronto ({count} pedidos carregados).")
    yield

app = FastAPI(
    title="Nex — Copiloto de Operações de Delivery",
    description="API do copiloto inteligente para triagem operacional e supervisão humana de pedidos.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS para o Frontend React / Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # No ambiente local de desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(public_router)
app.include_router(internal_router)

@app.get("/health", tags=["Healthcheck"])
def healthcheck():
    """Healthcheck simples para monitoramento do serviço e Compose."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "nex-backend-api",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

from fastapi.staticfiles import StaticFiles

# Se o build do frontend existir, servir estaticamente na raiz
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
