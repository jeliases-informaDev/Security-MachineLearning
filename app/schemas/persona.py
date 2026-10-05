import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoVerificacion, OrigenPersona, TipoDocumento


class PersonaBase(BaseModel):
    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = None
    nombres: str
    apellidos: str
    nombres_alternativos: list[str] = []
    fecha_nacimiento: date | None = None
    es_pep: bool = False
    cargo_pep: str | None = None


class PersonaOut(PersonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: uuid.UUID | None
    nivel_riesgo_score: float
    origen: OrigenPersona
    estado_verificacion: EstadoVerificacion
    creado_en: datetime
    actualizado_en: datetime
