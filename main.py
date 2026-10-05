from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.indira import router as indira_router
from app.api.personas import router as personas_router
from app.api.tickets import router as tickets_router
from app.api.vigilancia import router as vigilancia_router
from app.core.config import settings
from app.core.security import verificar_clave_interna
from app.services.scheduler_service import detener_scheduler, iniciar_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    iniciar_scheduler()
    yield
    detener_scheduler()


app = FastAPI(
    title="Security - ML & Scraping API",
    description="Microservicio para Scoring de Riesgos, casos en prensa y el agente Indira.",
    version="1.0.0",
    lifespan=lifespan,
)

# Solo el backend Kotlin (y el entorno de desarrollo) deberían llamar a este servicio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "online", "service": "Security Machine Learning Engine"}


@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "message": "Microservicio listo para recibir peticiones"}


# Todas las rutas de negocio exigen la clave interna compartida con el backend Kotlin.
rutas_internas = [Depends(verificar_clave_interna)]
app.include_router(personas_router, dependencies=rutas_internas)
app.include_router(tickets_router, dependencies=rutas_internas)
app.include_router(indira_router, dependencies=rutas_internas)
app.include_router(vigilancia_router, dependencies=rutas_internas)

# Página de prueba del chat: solo en desarrollo, porque no envía la clave interna.
if settings.ENTORNO == "dev":
    app.mount("/indira-chat", StaticFiles(directory="app/static", html=True), name="indira-chat")
