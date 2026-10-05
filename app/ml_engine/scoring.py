from app.models.enums import EstadoRevision
from app.models.persona import Persona

PUNTOS_POR_PEP = 30.0
PUNTOS_POR_CASO_VERIFICADO = 15.0
TOPE_PUNTOS_CASOS = 60.0


def calcular_score_riesgo(persona: Persona) -> float:
    """Placeholder basado en reglas hasta contar con un modelo entrenado
    (pendiente en docs/ARQUITECTURA.md: umbral y taxonomía de categoria_delito)."""
    score = PUNTOS_POR_PEP if persona.es_pep else 0.0

    casos_verificados = [c for c in persona.casos if c.estado_revision == EstadoRevision.VERIFICADO]
    score += min(len(casos_verificados) * PUNTOS_POR_CASO_VERIFICADO, TOPE_PUNTOS_CASOS)

    return min(score, 100.0)
