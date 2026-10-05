import uuid

from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Fuente(Base):
    __tablename__ = "fuentes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(150))
    dominio: Mapped[str] = mapped_column(String(255), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    config_scraper: Mapped[dict] = mapped_column(JSON, default=dict)
    frecuencia_minutos: Mapped[int] = mapped_column(Integer, default=60)

    articulos: Mapped[list["ArticuloRaw"]] = relationship(back_populates="fuente")
