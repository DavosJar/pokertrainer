import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import APP_ENV, DB_PATH, engine, Base, SessionLocal
from app.services.importer import sync_all_scenarios
from app.routers import scenarios, training, stats, views

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Dejar constancia de contra qué BD se está escribiendo.
    print(f"[STARTUP] APP_ENV={APP_ENV}  DB={DB_PATH}")

    # 1. Crear tablas en SQLite si no existen
    Base.metadata.create_all(bind=engine)

    # 2. Sincronizar automáticamente los escenarios desde /data/scenarios/*.json
    db = SessionLocal()
    try:
        result = sync_all_scenarios(db)
        print(f"[STARTUP] Escenarios sincronizados: {result['synced']}/{result['total_files']}. Errores: {len(result['errors'])}")
        if result['errors']:
            for err in result['errors']:
                print(f"[STARTUP ERROR] {err}")
    finally:
        db.close()

    yield


app = FastAPI(
    title="Spin & Go Preflop Range Trainer",
    description="Entrenador de rangos preflop de alta velocidad para Spin & Go (3-max: BTN, SB, BB)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos (JS compilado, CSS, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Incluir routers
app.include_router(views.router)
app.include_router(scenarios.router)
app.include_router(training.router)
app.include_router(stats.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
