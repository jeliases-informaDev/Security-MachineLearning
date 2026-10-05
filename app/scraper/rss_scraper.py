import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from app.scraper.base import ArticuloExtraido, Scraper


class RSSScraper(Scraper):
    """Scraper genérico para cualquier Fuente que exponga un feed RSS 2.0.

    La url del feed viene de Fuente.config_scraper, ej:
    {"tipo": "rss", "feed_url": "https://rpp.pe/feed"}
    """

    def __init__(self, feed_url: str, timeout: int = 15):
        self.feed_url = feed_url
        self.timeout = timeout

    def obtener_articulos(self) -> list[ArticuloExtraido]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SecurityMLBot/1.0)"}
        response = requests.get(self.feed_url, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        articulos = []
        for item in root.iter("item"):
            link = _texto(item.find("link"))
            titulo = _texto(item.find("title"))
            if not link or not titulo:
                continue

            articulos.append(
                ArticuloExtraido(
                    url=link,
                    titulo=titulo,
                    contenido_texto=_texto(item.find("description")) or "",
                    fecha_publicacion=_parsear_fecha(_texto(item.find("pubDate"))),
                )
            )
        return articulos


def _texto(elemento: ET.Element | None) -> str | None:
    if elemento is None or elemento.text is None:
        return None
    return elemento.text.strip()


def _parsear_fecha(valor: str | None):
    if not valor:
        return None
    try:
        return parsedate_to_datetime(valor).date()
    except (TypeError, ValueError):
        return None
