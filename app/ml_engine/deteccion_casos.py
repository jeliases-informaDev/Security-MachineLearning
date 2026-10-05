import json

import ollama
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.articulo import ArticuloRaw
from app.models.enums import TipoCaso
from app.models.persona import Persona
from app.services.casos_service import procesar_mencion

# Por debajo del UMBRAL_AUTO_VERIFICACION de casos_service: todo lo detectado
# automaticamente queda pendiente de revision humana, nunca se auto-publica.
SCORE_CONFIANZA_AUTOMATICA = 0.6

PROMPT_DETECCION = """Eres un analista que revisa articulos de prensa para un sistema de compliance/AML.
Se te da el titulo y el resumen de una noticia, y el nombre de una persona que aparece mencionada en el texto.
Determina si la noticia describe una acusacion, denuncia, investigacion, sentencia o absolucion PENAL O DISCIPLINARIA
relacionada especificamente con esa persona (no basta con que salga mencionada; tiene que tratarse de un caso legal).

Responde EXCLUSIVAMENTE con JSON, sin texto adicional, con este formato exacto:
{"es_caso": true o false, "tipo": "acusacion|denuncia|investigacion|sentencia|absolucion", "categoria_delito": "...", "resumen": "..."}

Si es_caso es false, deja "tipo", "categoria_delito" y "resumen" como cadenas vacias.
"""


def _detectar_caso_en_texto(persona_nombre_completo: str, titulo: str, texto: str) -> dict | None:
    cliente = ollama.Client(host=settings.OLLAMA_BASE_URL)
    try:
        respuesta = cliente.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_DETECCION},
                {"role": "user", "content": f"Persona: {persona_nombre_completo}\nTitulo: {titulo}\nResumen: {texto}"},
            ],
            format="json",
        )
    except Exception:
        # El motor local puede no estar disponible (Ollama caido, modelo no descargado, etc.);
        # el job diario no debe romperse por eso, simplemente se salta la deteccion.
        return None

    try:
        datos = json.loads(respuesta.message.content)
    except (json.JSONDecodeError, TypeError):
        return None

    if not datos.get("es_caso"):
        return None
    if datos.get("tipo") not in {t.value for t in TipoCaso}:
        return None
    return datos


def procesar_articulos_pendientes(db: Session, limite: int = 50) -> int:
    """Recorre articulos sin procesar, busca menciones a personas ya registradas
    (coincidencia de nombre completo) y usa el modelo local para decidir si el
    articulo describe un caso real. Todo lo creado aqui queda con score bajo,
    por lo que requiere revision humana antes de considerarse verificado."""
    personas = db.scalars(select(Persona)).all()
    articulos = db.scalars(select(ArticuloRaw).where(ArticuloRaw.procesado.is_(False)).limit(limite)).all()

    casos_creados = 0
    for articulo in articulos:
        texto_articulo = f"{articulo.titulo} {articulo.contenido_texto}".lower()

        for persona in personas:
            nombre_completo = f"{persona.nombres} {persona.apellidos}"
            if nombre_completo.lower() not in texto_articulo:
                continue

            resultado = _detectar_caso_en_texto(nombre_completo, articulo.titulo, articulo.contenido_texto)
            if resultado is None:
                continue

            procesar_mencion(
                db,
                articulo,
                nombres=persona.nombres,
                apellidos=persona.apellidos,
                tipo=TipoCaso(resultado["tipo"]),
                categoria_delito=resultado.get("categoria_delito") or "sin_clasificar",
                resumen=resultado.get("resumen") or "",
                score_confianza=SCORE_CONFIANZA_AUTOMATICA,
            )
            casos_creados += 1

        articulo.procesado = True
        db.add(articulo)

    db.commit()
    return casos_creados
