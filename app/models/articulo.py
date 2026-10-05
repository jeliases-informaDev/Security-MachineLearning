import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ArticuloRaw(Base):
    __tablename__ = "articulos_raw"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fuente_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fuentes.id"))

    url: Mapped[str] = mapped_column(String(1000), unique=True)
    hash_contenido: Mapped[str] = mapped_column(String(64), index=True)

    titulo: Mapped[str] = mapped_column(Text)
    contenido_texto: Mapped[str] = mapped_column(Text)

    fecha_publicacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_scrapeo: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    procesado: Mapped[bool] = mapped_column(Boolean, default=False)

    fuente: Mapped["Fuente"] = relationship(back_populates="articulos")
    casos: Mapped[list["Caso"]] = relationship(back_populates="articulo")
