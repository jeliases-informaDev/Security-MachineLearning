import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoRevision, TipoCaso


class Caso(Base):
    __tablename__ = "casos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("articulos_raw.id"))

    tipo: Mapped[TipoCaso] = mapped_column(SAEnum(TipoCaso, name="tipo_caso"))
    categoria_delito: Mapped[str] = mapped_column(String(150))
    resumen: Mapped[str] = mapped_column(Text)
    url_fuente: Mapped[str] = mapped_column(String(1000))

    score_confianza: Mapped[float] = mapped_column(Float, default=0.0)
    estado_revision: Mapped[EstadoRevision] = mapped_column(
        SAEnum(EstadoRevision, name="estado_revision_caso"), default=EstadoRevision.PENDIENTE
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    persona: Mapped["Persona"] = relationship(back_populates="casos")
    articulo: Mapped["ArticuloRaw"] = relationship(back_populates="casos")
