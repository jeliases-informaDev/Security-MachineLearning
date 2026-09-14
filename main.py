from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ComplyTools - ML & Scraping API",
    description="Microservicio para Scoring de Riesgos y validación en Listas Negativas.",
    version="1.0.0"
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