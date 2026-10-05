import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AutorMensajeTicket,
    CanalTicket,
    CreadoPorTicket,
    EstadoTicket,
    PrioridadTicket,
    TipoTicket,
)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    canal: Mapped[CanalTicket] = mapped_column(SAEnum(CanalTicket, name="canal_ticket"))
    tipo: Mapped[TipoTicket] = mapped_column(SAEnum(TipoTicket, name="tipo_ticket"))
    asunto: Mapped[str] = mapped_column(String(255))
    estado: Mapped[EstadoTicket] = mapped_column(SAEnum(EstadoTicket, name="estado_ticket"), default=EstadoTicket.ABIERTO)
    prioridad: Mapped[PrioridadTicket] = mapped_column(
        SAEnum(PrioridadTicket, name="prioridad_ticket"), default=PrioridadTicket.MEDIA
    )
    creado_por: Mapped[CreadoPorTicket] = mapped_column(SAEnum(CreadoPorTicket, name="creado_por_ticket"))

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    mensajes: Mapped[list["MensajeTicket"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class MensajeTicket(Base):
    __tablename__ = "mensajes_ticket"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))

    autor: Mapped[AutorMensajeTicket] = mapped_column(SAEnum(AutorMensajeTicket, name="autor_mensaje_ticket"))
    contenido: Mapped[str] = mapped_column(Text)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="mensajes")
