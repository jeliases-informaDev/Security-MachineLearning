from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.indira import router as indira_router
from app.api.personas import router as personas_router
from app.api.tickets import router as tickets_router
from app.services.scheduler_service import detener_scheduler, iniciar_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    iniciar_scheduler()
    yield
    detener_scheduler()


app = FastAPI(
    title="ComplyTools - ML & Scraping API",
    description="Microservicio para Scoring de Riesgos y validación en Listas Negativas.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS para permitir la comunicación con tu ecosistema
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se restringe a la IP/Red de tu backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "online", "service": "Security Machine Learning Engine"}

@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "message": "Microservicio listo para recibir peticiones"}


app.include_router(personas_router)
app.include_router(tickets_router)
app.include_router(indira_router)

app.mount("/indira-chat", StaticFiles(directory="app/static", html=True), name="indira-chat")