import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.articulo import ArticuloRaw
from app.models.fuente import Fuente
from app.scraper.base import ArticuloExtraido, Scraper


def _hash_contenido(titulo: str, contenido: str) -> str:
    return hashlib.sha256(f"{titulo}|{contenido}".encode("utf-8")).hexdigest()


def guardar_articulo_si_nuevo(db: Session, fuente: Fuente, articulo: ArticuloExtraido) -> ArticuloRaw | None:
    existente = db.scalar(select(ArticuloRaw).where(ArticuloRaw.url == articulo.url))
    if existente is not None:
        return None

    nuevo = ArticuloRaw(
        fuente_id=fuente.id,
        url=articulo.url,
        hash_contenido=_hash_contenido(articulo.titulo, articulo.contenido_texto),
        titulo=articulo.titulo,
        contenido_texto=articulo.contenido_texto,
        fecha_publicacion=articulo.fecha_publicacion,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def ejecutar_scraping_fuente(db: Session, fuente: Fuente, scraper: Scraper) -> list[ArticuloRaw]:
    guardados = []
    for articulo in scraper.obtener_articulos():
        registro = guardar_articulo_si_nuevo(db, fuente, articulo)
        if registro is not None:
            guardados.append(registro)
    return guardados
