from fastapi import APIRouter, HTTPException

from app.services import scheduler_service
from app.services.vigilancia_service import estado

router = APIRouter(prefix="/api/v1/vigilancia", tags=["vigilancia"])


@router.post("/ejecutar", status_code=202)
def ejecutar_vigilancia():
    """Lanza ahora la misma corrida que se ejecuta a diario (RSS + vigilancia por persona).

    Responde de inmediato: la corrida tarda varios minutos y sigue en segundo plano.
    Consulta el avance con GET /api/v1/vigilancia/estado.
    """
    if estado["en_curso"]:
        raise HTTPException(status_code=409, detail="Ya hay una vigilancia en curso")
    scheduler_service.ejecutar_ahora()
    return {"estado": "programada"}


@router.get("/estado")
def estado_vigilancia():
    ultimo = scheduler_service.ultimo_scrapeo()
    return {**estado, "ultimo_scrapeo": ultimo.isoformat() if ultimo else None}
