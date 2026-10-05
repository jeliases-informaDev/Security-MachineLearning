import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AutorMensajeTicket, CanalTicket, EstadoTicket, PrioridadTicket, TipoTicket


class TicketCreate(BaseModel):
    usuario_id: uuid.UUID
    canal: CanalTicket
    tipo: TipoTicket
    asunto: str
    prioridad: PrioridadTicket = PrioridadTicket.MEDIA


class MensajeTicketCreate(BaseModel):
    autor: AutorMensajeTicket
    contenido: str


class MensajeTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    autor: AutorMensajeTicket
    contenido: str
    creado_en: datetime


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    canal: CanalTicket
    tipo: TipoTicket
    asunto: str
    estado: EstadoTicket
    prioridad: PrioridadTicket
    creado_en: datetime
    actualizado_en: datetime
