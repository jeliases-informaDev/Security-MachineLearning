from dataclasses import dataclass
from datetime import date


@dataclass
class ArticuloExtraido:
    url: str
    titulo: str
    contenido_texto: str
    fecha_publicacion: date | None


class Scraper:
    def obtener_articulos(self) -> list[ArticuloExtraido]:
        raise NotImplementedError
