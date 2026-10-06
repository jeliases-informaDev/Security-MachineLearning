from sqlalchemy.orm import Session

from app.ml_engine.matching import buscar_persona_similar
from app.ml_engine.scoring import calcular_score_riesgo
from app.models.articulo import ArticuloRaw
from app.models.caso import Caso
from app.models.enums import EstadoRevision, EstadoVerificacion, OrigenPersona, TipoCaso
from app.models.persona import Persona

UMBRAL_AUTO_VERIFICACION = 0.85


def procesar_mencion(
    db: Session,
    articulo: ArticuloRaw,
    nombres: str,
    apellidos: str,
    tipo: TipoCaso,
    categoria_delito: str,
    resumen: str,
    score_confianza: float,
    numero_documento: str | None = None,
    persona: Persona | None = None,
) -> Caso:
    """Punto de entrada del `services` layer: dado un articulo y una mención de persona
    ya extraída (nombres/apellidos/tipo/categoría), crea o vincula la Persona y el Caso.

    La extracción de la mención en sí (NER sobre el texto crudo) es un paso previo
    pendiente de implementar — ver "Taxonomía de categoria_delito" en docs/ARQUITECTURA.md.
    """
    # Si el llamador ya sabe de quién se trata (p. ej. la vigilancia busca por persona),
    # no hace falta la búsqueda aproximada, que podría confundir a dos personas parecidas.
    if persona is None:
        persona = buscar_persona_similar(db, nombres, apellidos, numero_documento)

    if persona is None:
        persona = Persona(
            nombres=nombres,
            apellidos=apellidos,
            numero_documento=numero_documento,
            origen=OrigenPersona.SCRAPER_DETECTADO,
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        )
        db.add(persona)
        db.flush()

    estado_revision = (
        EstadoRevision.VERIFICADO if score_confianza >= UMBRAL_AUTO_VERIFICACION else EstadoRevision.PENDIENTE
    )

    caso = Caso(
        persona_id=persona.id,
        articulo_id=articulo.id,
        tipo=tipo,
        categoria_delito=categoria_delito,
        resumen=resumen,
        url_fuente=articulo.url,
        score_confianza=score_confianza,
        estado_revision=estado_revision,
    )
    db.add(caso)
    articulo.procesado = True
    db.flush()

    persona.nivel_riesgo_score = calcular_score_riesgo(persona)

    db.commit()
    db.refresh(caso)
    return caso
