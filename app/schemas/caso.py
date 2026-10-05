import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoRevision, TipoCaso


class CasoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    persona_id: uuid.UUID
    articulo_id: uuid.UUID

    tipo: TipoCaso
    categoria_delito: str
    resumen: str
    url_fuente: str

    score_confianza: float
    estado_revision: EstadoRevision

    creado_en: datetime
