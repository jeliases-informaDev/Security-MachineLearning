"""Vigilancia diaria de personas en la prensa.

Para cada persona registrada busca noticias recientes en diarios nacionales, descarta
las que no hablan de un tema judicial o fiscal, obtiene el enlace directo a la nota y
le pide al modelo local que decida si es un caso de esa persona. Nada se publica solo:
todo caso detectado queda pendiente de revisión humana y enlazado a su nota original.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.ml_engine.deteccion_casos import (
    SCORE_CONFIANZA_AUTOMATICA,
    ModeloNoDisponible,
    detectar_caso_en_texto,
    es_solo_denunciante,
)
from app.ml_engine.nombres import menciona_persona, nombre_para_busqueda, normalizar
from app.models.articulo import ArticuloRaw
from app.models.caso import Caso
from app.models.enums import EstadoVerificacion, TipoCaso
from app.models.fuente import Fuente
from app.models.persona import Persona
from app.scraper.base import ArticuloExtraido
from app.scraper.google_news import (
    USER_AGENT,
    NoticiaEncontrada,
    buscar_noticias,
    construir_consulta,
    dominio_de,
    es_diario_reconocido,
    resolver_url,
)
from app.services.articulos_service import guardar_articulo_si_nuevo
from app.services.casos_service import procesar_mencion

# Raíces (sin tildes) de palabras que delatan un tema judicial o fiscal en un titular.
# Es un filtro barato para no gastar al modelo en noticias que claramente no lo son.
RAICES_JUDICIALES = (
    "investig", "denunci", "fiscal", "acusa", "sentenc", "conden", "juicio", "prision", "preventiv",
    "lavado", "corrupci", "colusi", "cohecho", "peculado", "organizacion criminal", "impedimento de salida",
    "extradic", "absuel", "archiv", "imput", "procesad", "detenc", "captura", "delito", "proceso penal",
    "audiencia", "colaboracion eficaz", "pena", "culpable", "poder judicial", "tribunal", "juez",
)

LIMITE_DESCRIPCION = 600


@dataclass
class ResultadoVigilancia:
    personas_revisadas: int = 0
    noticias_encontradas: int = 0
    candidatas: int = 0
    articulos_nuevos: int = 0
    casos_creados: int = 0
    modelo_disponible: bool = True
    errores: list[str] = field(default_factory=list)


class VigilanciaEnCurso(Exception):
    """Ya hay una vigilancia ejecutándose; no se lanza otra en paralelo."""


_candado = threading.Lock()
estado: dict = {"en_curso": False, "inicio": None, "fin": None, "resultado": None}


def tiene_tema_judicial(titulo: str) -> bool:
    texto = normalizar(titulo)
    return any(raiz in texto for raiz in RAICES_JUDICIALES)


def _menciona_a(titulo: str, persona: Persona) -> bool:
    """Filtro barato sobre el titular, antes de resolver el enlace: lo nombra por su nombre o
    por un apellido que no es de otra persona (los titulares abrevian: "Boluarte: Fiscalía abre...")."""
    return menciona_persona(titulo, "", persona)


def descripcion_de_pagina(url: str, timeout: int = 10) -> str:
    """Resumen que el propio diario pone en la nota (meta description), si se puede leer."""
    try:
        respuesta = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        if respuesta.status_code != 200:
            return ""
        sopa = BeautifulSoup(respuesta.text, "html.parser")
        for atributos in ({"property": "og:description"}, {"name": "description"}):
            etiqueta = sopa.find("meta", attrs=atributos)
            contenido = (etiqueta.get("content") or "").strip() if etiqueta else ""
            if contenido:
                return contenido[:LIMITE_DESCRIPCION]
    except requests.RequestException:
        pass
    return ""


def _fuente_para(db: Session, diario: str, dominio: str) -> Fuente:
    fuente = db.scalar(select(Fuente).where(Fuente.dominio == dominio))
    if fuente is None:
        fuente = Fuente(nombre=diario or dominio, dominio=dominio, config_scraper={"tipo": "google_news"})
        db.add(fuente)
        db.commit()
        db.refresh(fuente)
    return fuente


def _articulo_conocido(db: Session, noticia: NoticiaEncontrada) -> ArticuloRaw | None:
    """Artículo ya guardado con el mismo título en el mismo diario (evita resolver su enlace de nuevo)."""
    return db.scalar(
        select(ArticuloRaw)
        .join(Fuente, Fuente.id == ArticuloRaw.fuente_id)
        .where(Fuente.dominio == noticia.dominio, ArticuloRaw.titulo == noticia.titulo)
    )


def _caso_existente(db: Session, persona: Persona, articulo: ArticuloRaw) -> bool:
    return (
        db.scalar(select(Caso.id).where(Caso.persona_id == persona.id, Caso.articulo_id == articulo.id)) is not None
    )


def vigilar_persona(
    db: Session,
    persona: Persona,
    dias: int,
    max_por_persona: int,
    pausa: float,
    resultado: ResultadoVigilancia,
    log: Callable[[str], None],
) -> None:
    nombre = nombre_para_busqueda(persona)
    noticias = buscar_noticias(construir_consulta(nombre, dias))
    resultado.noticias_encontradas += len(noticias)

    candidatas = [
        n
        for n in noticias
        if es_diario_reconocido(n.dominio) and _menciona_a(n.titulo, persona) and tiene_tema_judicial(n.titulo)
    ][:max_por_persona]
    resultado.candidatas += len(candidatas)
    log(f"  {nombre}: {len(noticias)} noticias, {len(candidatas)} candidatas")

    nombre_completo = f"{persona.nombres} {persona.apellidos}"
    for noticia in candidatas:
        articulo = _articulo_conocido(db, noticia)

        if articulo is None:
            time.sleep(pausa)
            url = resolver_url(noticia.url_google)
            # Solo se guarda el enlace directo al diario; si no se pudo resolver, se descarta.
            if url is None or not es_diario_reconocido(dominio_de(url)):
                continue

            descripcion = descripcion_de_pagina(url)
            texto = f"{noticia.titulo}. {descripcion}" if descripcion else noticia.titulo
            fuente = _fuente_para(db, noticia.diario, dominio_de(url))
            articulo = guardar_articulo_si_nuevo(
                db, fuente, ArticuloExtraido(url=url, titulo=noticia.titulo, contenido_texto=texto, fecha_publicacion=noticia.fecha)
            )
            if articulo is None:  # la misma nota ya existía con otro título
                continue
            resultado.articulos_nuevos += 1

        if _caso_existente(db, persona, articulo):
            continue

        # Con el resumen de la nota ya a la vista: tiene que hablar de ESTA persona (no de un
        # homónimo que comparte apellido) y no mostrarla como quien denuncia en vez de la denunciada.
        texto_nota = f"{articulo.titulo} {articulo.contenido_texto}"
        if not menciona_persona(articulo.titulo, articulo.contenido_texto, persona) or es_solo_denunciante(
            texto_nota, persona
        ):
            continue

        # Si el modelo no responde, el artículo queda sin procesar y se reintenta en la próxima corrida.
        deteccion = detectar_caso_en_texto(nombre_completo, articulo.titulo, articulo.contenido_texto, lanzar_si_falla=True)
        if deteccion is None:
            articulo.procesado = True
            db.add(articulo)
            db.commit()
            continue

        procesar_mencion(
            db,
            articulo,
            nombres=persona.nombres,
            apellidos=persona.apellidos,
            tipo=TipoCaso(deteccion["tipo"]),
            categoria_delito=deteccion.get("categoria_delito") or "sin_clasificar",
            resumen=deteccion.get("resumen") or articulo.titulo,
            score_confianza=SCORE_CONFIANZA_AUTOMATICA,
            persona=persona,
        )
        resultado.casos_creados += 1
        log(f"    caso [{deteccion['tipo']}] {articulo.titulo[:90]}")


def ejecutar_vigilancia(
    db: Session,
    dias: int = 30,
    max_por_persona: int = 6,
    pausa: float = 0.6,
    log: Callable[[str], None] = print,
    solo: str | None = None,
) -> ResultadoVigilancia:
    """Vigila a todas las personas registradas (salvo las descartadas).

    `solo` limita la corrida a las personas cuyo nombre contiene ese texto (para pruebas).
    """
    resultado = ResultadoVigilancia()
    personas = db.scalars(
        select(Persona)
        .where(Persona.estado_verificacion != EstadoVerificacion.DESCARTADO)
        .order_by(Persona.apellidos, Persona.nombres)
    ).all()
    if solo:
        filtro = normalizar(solo)
        personas = [p for p in personas if filtro in normalizar(f"{p.nombres} {p.apellidos}")]

    for persona in personas:
        try:
            vigilar_persona(db, persona, dias, max_por_persona, pausa, resultado, log)
        except ModeloNoDisponible as exc:
            resultado.modelo_disponible = False
            resultado.errores.append(f"Modelo no disponible: {exc}")
            log("  El modelo local no responde; se detiene la vigilancia (se reintentará en la próxima corrida).")
            break
        except (requests.RequestException, SQLAlchemyError) as exc:
            # Un fallo de red o de base de datos con una persona no debe frenar al resto.
            db.rollback()
            resultado.errores.append(f"{persona.nombres} {persona.apellidos}: {type(exc).__name__}")
            log(f"  Error con {persona.nombres} {persona.apellidos}: {type(exc).__name__}: {exc}")
        resultado.personas_revisadas += 1
        time.sleep(pausa)

    return resultado


def ejecutar_vigilancia_en_sesion(
    dias: int = 30, max_por_persona: int = 6, log: Callable[[str], None] = print
) -> ResultadoVigilancia:
    """Abre su propia sesión, evita corridas simultáneas y deja el resultado en `estado`."""
    if not _candado.acquire(blocking=False):
        raise VigilanciaEnCurso()

    estado.update(en_curso=True, inicio=datetime.now(timezone.utc).isoformat(), fin=None, resultado=None)
    db = SessionLocal()
    try:
        resultado = ejecutar_vigilancia(db, dias=dias, max_por_persona=max_por_persona, log=log)
        estado["resultado"] = asdict(resultado)
        return resultado
    finally:
        db.close()
        estado.update(en_curso=False, fin=datetime.now(timezone.utc).isoformat())
        _candado.release()
