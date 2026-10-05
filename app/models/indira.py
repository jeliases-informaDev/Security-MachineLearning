import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CanalConversacion, EstadoConversacion, FeedbackMensaje, FormatoReporte, RolMensaje


class ConversacionIndira(Base):
    __tablename__ = "conversaciones_indira"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    canal: Mapped[CanalConversacion] = mapped_column(SAEnum(CanalConversacion, name="canal_conversacion"))
    estado: Mapped[EstadoConversacion] = mapped_column(
        SAEnum(EstadoConversacion, name="estado_conversacion"), default=EstadoConversacion.ACTIVA
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mensajes: Mapped[list["MensajeIndira"]] = relationship(
        back_populates="conversacion", cascade="all, delete-orphan"
    )


class MensajeIndira(Base):
    __tablename__ = "mensajes_indira"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversacion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversaciones_indira.id"))

    rol: Mapped[RolMensaje] = mapped_column(SAEnum(RolMensaje, name="rol_mensaje_indira"))
    contenido: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tokens_usados: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[FeedbackMensaje | None] = mapped_column(
        SAEnum(FeedbackMensaje, name="feedback_mensaje_indira"), nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversacion: Mapped["ConversacionIndira"] = relationship(back_populates="mensajes")


class EjemploVerificado(Base):
    """Pares pregunta/respuesta que un usuario marco como utiles (feedback positivo).
    Sirven de memoria: se recuperan por similitud y se inyectan como ejemplos en
    conversaciones futuras, sin necesidad de reentrenar el modelo."""

    __tablename__ = "ejemplos_verificados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mensajes_indira.id"), nullable=True
    )

    pregunta_usuario: Mapped[str] = mapped_column(Text)
    respuesta_indira: Mapped[str] = mapped_column(Text)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReporteGenerado(Base):
    __tablename__ = "reportes_generados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solicitado_por_usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    conversacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversaciones_indira.id"), nullable=True
    )

    tipo_reporte: Mapped[str] = mapped_column(String(150))
    formato: Mapped[FormatoReporte] = mapped_column(SAEnum(FormatoReporte, name="formato_reporte"))
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    url_archivo: Mapped[str] = mapped_column(String(1000))

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
