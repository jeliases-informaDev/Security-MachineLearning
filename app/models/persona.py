import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, Float, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoVerificacion, OrigenPersona, TipoDocumento


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    tipo_documento: Mapped[TipoDocumento | None] = mapped_column(
        SAEnum(TipoDocumento, name="tipo_documento"), nullable=True
    )
    numero_documento: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    nombres: Mapped[str] = mapped_column(String(200))
    apellidos: Mapped[str] = mapped_column(String(200))
    nombres_alternativos: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)

    es_pep: Mapped[bool] = mapped_column(Boolean, default=False)
    cargo_pep: Mapped[str | None] = mapped_column(String(200), nullable=True)

    nivel_riesgo_score: Mapped[float] = mapped_column(Float, default=0.0)

    origen: Mapped[OrigenPersona] = mapped_column(
        SAEnum(OrigenPersona, name="origen_persona"), default=OrigenPersona.SCRAPER_DETECTADO
    )
    estado_verificacion: Mapped[EstadoVerificacion] = mapped_column(
        SAEnum(EstadoVerificacion, name="estado_verificacion_persona"), default=EstadoVerificacion.PENDIENTE
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    casos: Mapped[list["Caso"]] = relationship(back_populates="persona")
