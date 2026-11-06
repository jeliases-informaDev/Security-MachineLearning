from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml_engine.nombres import normalizar
from app.models.persona import Persona

UMBRAL_COINCIDENCIA = 90.0


def buscar_persona_similar(
    db: Session, nombres: str, apellidos: str, numero_documento: str | None = None
) -> Persona | None:
    if numero_documento:
        persona = db.scalar(select(Persona).where(Persona.numero_documento == numero_documento))
        if persona is not None:
            return persona

    nombre_completo = f"{nombres} {apellidos}".strip().lower()
    mejor_persona = None
    mejor_score = 0.0

    # Comparación en memoria contra toda la tabla: aceptable al tamaño actual de datos,
    # a optimizar con búsqueda por trigramas (pg_trgm) cuando la tabla de Persona crezca.
    for persona in db.scalars(select(Persona)):
        candidatos = [
            f"{persona.nombres} {persona.apellidos}".lower(),
            *[alt.lower() for alt in persona.nombres_alternativos],
        ]
        score = max(fuzz.token_sort_ratio(nombre_completo, candidato) for candidato in candidatos)
        if score > mejor_score:
            mejor_score = score
            mejor_persona = persona

    if mejor_score >= UMBRAL_COINCIDENCIA:
        return mejor_persona
    return None


def elegir_persona(personas, texto: str, umbral: float = 75.0):
    """Devuelve la persona mas parecida a `texto` (o None si ninguna llega al umbral).

    Compara sin tildes ni mayusculas: "cerron" encuentra a "Cerrón". Si varias personas
    comparten el apellido (p. ej. Humala), devuelve la de mayor parecido.
    """
    texto_normalizado = normalizar(texto)
    mejor_persona = None
    mejor_score = 0.0

    for persona in personas:
        candidatos = [
            normalizar(f"{persona.nombres} {persona.apellidos}"),
            *[normalizar(alt) for alt in persona.nombres_alternativos],
        ]
        score = max(fuzz.token_set_ratio(texto_normalizado, candidato) for candidato in candidatos)
        if score > mejor_score:
            mejor_score = score
            mejor_persona = persona

    return mejor_persona if mejor_score >= umbral else None


def buscar_persona_por_texto(db: Session, texto: str, umbral: float = 75.0) -> Persona | None:
    """Búsqueda de una Persona a partir de un texto libre (nombre completo o
    número de documento), pensada para que la use el agente Indira desde el chat."""
    texto = texto.strip()
    if texto.isdigit():
        persona = db.scalar(select(Persona).where(Persona.numero_documento == texto))
        if persona is not None:
            return persona

    return elegir_persona(db.scalars(select(Persona)), texto, umbral)
