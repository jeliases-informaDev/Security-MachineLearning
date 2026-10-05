import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def verificar_clave_interna(x_internal_key: str | None = Header(default=None)) -> None:
    """Exige el header X-Internal-Key en las rutas internas (las llama el backend Kotlin)."""
    if not settings.INTERNAL_API_KEY:
        if settings.ENTORNO == "dev":
            return
        logger.error("INTERNAL_API_KEY no está configurada en un entorno que no es dev")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Servicio no configurado")

    if x_internal_key is None or not hmac.compare_digest(x_internal_key, settings.INTERNAL_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave interna inválida")
