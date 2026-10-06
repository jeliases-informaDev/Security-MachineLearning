"""Búsqueda de noticias por persona usando el buscador de Google Noticias (RSS público).

Los diarios solo publican en su RSS las últimas noticias; para vigilar a una persona
concreta hace falta buscar por su nombre. Este módulo hace esa búsqueda y devuelve
solo medios de alcance nacional reconocidos, con el enlace directo a la nota.
"""

import json
import re
import time
import urllib.parse as up
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Medios de alcance nacional, reconocidos. Se excluyen a propósito redes sociales,
# blogs, agregadores y prensa sensacionalista: un caso solo se registra si lo reporta
# uno de estos medios.
DOMINIOS_RECONOCIDOS: frozenset[str] = frozenset(
    {
        "elcomercio.pe",
        "larepublica.pe",
        "peru21.pe",
        "gestion.pe",
        "diariocorreo.pe",
        "infobae.com",
        "rpp.pe",
        "andina.pe",
        "elperuano.pe",
        "exitosa.pe",
        "canaln.pe",
        "expreso.com.pe",
        "americatv.com.pe",
        "panamericana.pe",
        "latina.pe",
        "atv.pe",
        "caretas.pe",
        "ojo-publico.com",
        "convoca.pe",
        "idl-reporteros.pe",
    }
)

# Términos que acompañan al nombre en la consulta para traer noticias judiciales/fiscales.
TERMINOS_JUDICIALES = (
    "investigación",
    "fiscalía",
    "denuncia",
    "acusación",
    "sentencia",
    "juicio",
    "condena",
    '"lavado de activos"',
    "corrupción",
)

_URL_BUSQUEDA = "https://news.google.com/rss/search"
_URL_ARTICULO = "https://news.google.com/rss/articles/"
_URL_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je"


@dataclass
class NoticiaEncontrada:
    titulo: str
    url_google: str
    fecha: date | None
    diario: str
    dominio: str


def dominio_de(url: str) -> str:
    """Dominio en minúsculas y sin 'www.' ("https://www.RPP.pe/x" -> "rpp.pe")."""
    host = up.urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def es_diario_reconocido(dominio: str) -> bool:
    return any(dominio == d or dominio.endswith("." + d) for d in DOMINIOS_RECONOCIDOS)


def construir_consulta(nombre: str, dias: int) -> str:
    terminos = " OR ".join(TERMINOS_JUDICIALES)
    return f'"{nombre}" ({terminos}) when:{dias}d'


def _get(url: str, params: dict | None = None, timeout: int = 20, reintentos: int = 2) -> requests.Response:
    """GET con reintentos si el servidor pide bajar el ritmo (429) o falla (5xx)."""
    ultimo: requests.Response | None = None
    for intento in range(reintentos + 1):
        ultimo = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
        if ultimo.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(2 * (intento + 1))
    assert ultimo is not None
    ultimo.raise_for_status()
    return ultimo


def buscar_noticias(consulta: str, timeout: int = 20) -> list[NoticiaEncontrada]:
    """Busca noticias recientes en Google Noticias (Perú, español). Puede lanzar requests.RequestException."""
    respuesta = _get(
        _URL_BUSQUEDA,
        params={"q": consulta, "hl": "es-419", "gl": "PE", "ceid": "PE:es-419"},
        timeout=timeout,
    )
    raiz = ET.fromstring(respuesta.content)

    noticias: list[NoticiaEncontrada] = []
    for item in raiz.findall("./channel/item"):
        titulo = (item.findtext("title") or "").strip()
        enlace = (item.findtext("link") or "").strip()
        origen = item.find("source")
        if not titulo or not enlace or origen is None:
            continue

        diario = (origen.text or "").strip()
        dominio = dominio_de(origen.get("url") or "")
        if diario and titulo.endswith(f" - {diario}"):
            titulo = titulo[: -(len(diario) + 3)].strip()

        fecha: date | None = None
        publicada = item.findtext("pubDate")
        if publicada:
            try:
                fecha = parsedate_to_datetime(publicada).date()
            except (TypeError, ValueError):
                fecha = None

        noticias.append(NoticiaEncontrada(titulo=titulo, url_google=enlace, fecha=fecha, diario=diario, dominio=dominio))
    return noticias


def resolver_url(url_google: str, timeout: int = 20) -> str | None:
    """Obtiene el enlace directo a la nota del diario a partir del enlace de Google Noticias.

    Google no redirige con HTTP: la página trae una firma y una marca de tiempo con las
    que se consulta el mismo servicio interno que usa su web. Devuelve None si no se
    puede resolver (el formato de Google cambia de vez en cuando); el llamador debe
    descartar esa noticia en lugar de guardar un enlace indirecto.
    """
    try:
        id_articulo = url_google.split("/articles/")[1].split("?")[0]
        pagina = _get(_URL_ARTICULO + id_articulo, timeout=timeout)
        firma = re.search(r'data-n-a-sg="([^"]+)"', pagina.text)
        marca = re.search(r'data-n-a-ts="([^"]+)"', pagina.text)
        if not (firma and marca):
            return None

        interno = (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
            f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{id_articulo}",{marca.group(1)},"{firma.group(1)}"]'
        )
        respuesta = requests.post(
            _URL_BATCH,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data="f.req=" + up.quote(json.dumps([[["Fbv4je", interno]]])),
            timeout=timeout,
        )
        respuesta.raise_for_status()
        datos = json.loads(respuesta.text.split("\n\n")[1])
        url = json.loads(datos[0][2])[1]
    except (IndexError, KeyError, TypeError, ValueError, requests.RequestException):
        return None

    return url if isinstance(url, str) and url.startswith("http") else None
