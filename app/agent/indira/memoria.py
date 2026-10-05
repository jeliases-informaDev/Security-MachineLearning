from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.indira import EjemploVerificado

UMBRAL_SIMILITUD = 70.0


def buscar_ejemplos_similares(db: Session, pregunta: str, top_k: int = 2) -> list[EjemploVerificado]:
    """Recupera ejemplos previos verificados (feedback positivo) parecidos a la
    pregunta actual, para inyectarlos como contexto -- la parte de 'memoria' de
    Indira, sin tocar los pesos del modelo."""
    ejemplos = db.scalars(select(EjemploVerificado)).all()
    if not ejemplos:
        return []

    # WRatio combina varias heuristicas de rapidfuzz y tolera mejor las
    # preguntas parafraseadas que un simple token_set_ratio.
    puntuados = [(fuzz.WRatio(pregunta.lower(), ej.pregunta_usuario.lower()), ej) for ej in ejemplos]
    puntuados = [p for p in puntuados if p[0] >= UMBRAL_SIMILITUD]
    puntuados.sort(key=lambda p: p[0], reverse=True)

    return [ej for _, ej in puntuados[:top_k]]


def construir_contexto_memoria(ejemplos: list[EjemploVerificado]) -> str | None:
    if not ejemplos:
        return None

    bloques = [
        f"Pregunta: {ej.pregunta_usuario}\nRespuesta: {ej.respuesta_indira}" for ej in ejemplos
    ]
    return (
        "Estos son ejemplos de respuestas anteriores que los usuarios marcaron como utiles. "
        "Usalos como referencia de estilo y contenido cuando sean relevantes:\n\n" + "\n\n".join(bloques)
    )
