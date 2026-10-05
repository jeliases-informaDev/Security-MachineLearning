import json
import re

import ollama
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml_engine.nombres import normalizar, primer_apellido, se_menciona, variantes_nombre
from app.models.articulo import ArticuloRaw
from app.models.enums import TipoCaso
from app.models.persona import Persona
from app.services.casos_service import procesar_mencion

# Por debajo del UMBRAL_AUTO_VERIFICACION de casos_service: todo lo detectado
# automaticamente queda pendiente de revision humana, nunca se auto-publica.
SCORE_CONFIANZA_AUTOMATICA = 0.6

PROMPT_DETECCION = """Eres un analista que revisa titulares y resumenes de prensa para un sistema de compliance/AML.
Se te da el titulo y el resumen de una noticia, y el nombre de una persona mencionada en ella.
Determina si la noticia informa de una acusacion, denuncia, investigacion, sentencia o absolucion PENAL O DISCIPLINARIA
cuyo SUJETO es esa persona: ella es la investigada, denunciada, acusada, sentenciada o absuelta.

NO es un caso si la persona:
- solo aparece declarando, opinando o criticando a otros;
- es quien denuncia, la victima o un testigo;
- es el juez o el fiscal que conduce el caso de otra persona;
- se menciona de pasada o la noticia trata de otro tema (elecciones, encuestas, agenda politica);
- la noticia trata de una designacion, nombramiento, ascenso, renuncia o cese administrativo, salvo que
  diga expresamente que es una sancion disciplinaria.

Tipos (elige el mas cercano; si dudas, usa "investigacion"):
- investigacion: la fiscalia o el Poder Judicial investigan o procesan a la persona (incluye imputaciones,
  prision preventiva, impedimento de salida, ordenes de captura, audiencias y recursos sobre un caso abierto).
- denuncia: se presento una denuncia o querella contra la persona.
- acusacion: la fiscalia presento o pidio una acusacion formal (requerimiento acusatorio) contra la persona.
- sentencia: un juez dicto una sentencia o condena contra la persona.
- absolucion: SOLO si un juez absuelve a la persona o archiva/sobresee el caso. Retirar una orden de captura,
  rechazar un pedido o anular un tramite NO es una absolucion.

Usa unicamente lo que dice el texto: no agregues hechos, fechas ni delitos que no aparezcan en el.

Responde EXCLUSIVAMENTE con JSON, sin texto adicional, con este formato exacto:
{"es_caso": true o false, "tipo": "acusacion|denuncia|investigacion|sentencia|absolucion", "categoria_delito": "...", "resumen": "..."}

categoria_delito: el delito en minusculas y pocas palabras (por ejemplo "lavado de activos", "corrupcion",
"colusion", "organizacion criminal"); si el texto no lo dice, "sin_clasificar".
resumen: una sola oracion basada en el titulo.
Si es_caso es false, deja "tipo", "categoria_delito" y "resumen" como cadenas vacias.
"""


# Palabras (sin tildes) que el texto debe contener para sostener un tipo "fuerte".
# Un modelo pequeño a veces etiqueta de mas ("retiran orden de captura" -> absolucion);
# si el texto no trae evidencia del tipo, se baja a "investigacion", que es el mas neutro.
EVIDENCIA_POR_TIPO = {
    TipoCaso.ABSOLUCION: ("absuel", "archiv", "sobresei", "inocente", "libre de cargos"),
    TipoCaso.SENTENCIA: ("sentenci", "conden", "culpable", "anos de carcel", "anos de prision", "pena de"),
    TipoCaso.ACUSACION: ("acusa", "acusatorio"),
}


def ajustar_tipo(tipo: str, texto: str) -> str:
    """Devuelve `tipo`, o "investigacion" si es un tipo fuerte sin evidencia en el texto."""
    evidencia = EVIDENCIA_POR_TIPO.get(TipoCaso(tipo))
    if evidencia is None:
        return tipo
    normalizado = normalizar(texto)
    return tipo if any(palabra in normalizado for palabra in evidencia) else TipoCaso.INVESTIGACION.value


def es_solo_denunciante(texto: str, persona: Persona) -> bool:
    """True si el texto muestra a la persona como quien denuncia o querella, y no como el
    denunciado ("querella de César Acuña contra Fernando Olivera"). El modelo local falla
    con frecuencia en esto, y atribuirle a alguien un caso que él mismo inició es grave."""
    t = normalizar(texto)
    nombres = [*variantes_nombre(persona), primer_apellido(persona)]
    reclamante = any(
        re.search(rf"\b(querella|denuncia|demanda|queja|acusacion) de {re.escape(n)}\b", t)
        or re.search(rf"\b{re.escape(n)} (denuncia|demanda|querella|acusa|denuncio) (a|ante|al|contra)\b", t)
        for n in nombres
        if n
    )
    objetivo = any(
        re.search(rf"\bcontra {re.escape(n)}\b", t)
        or re.search(
            rf"\b(investigan|investiga|acusan|acusa|denuncian|condenan|procesan|sancionan|citan|imputan|"
            rf"sentencian|absuelven|requieren|piden|dictan)\s+(prision\s+\w+\s+)?(a|al|para) {re.escape(n)}\b",
            t,
        )
        for n in nombres
        if n
    )
    return reclamante and not objetivo


class ModeloNoDisponible(Exception):
    """El modelo local (Ollama) no respondio; no se pudo decidir si hay un caso."""


def detectar_caso_en_texto(
    persona_nombre_completo: str, titulo: str, texto: str, lanzar_si_falla: bool = False
) -> dict | None:
    """Pregunta al modelo local si la noticia describe un caso legal de la persona.

    Devuelve None si no hay caso. Si el modelo no esta disponible, devuelve None salvo que
    `lanzar_si_falla` sea True: asi un llamador que guarda estado (la vigilancia) puede
    distinguir "no hay caso" de "no se pudo decidir" y reintentar despues.
    """
    cliente = ollama.Client(host=settings.OLLAMA_BASE_URL)
    try:
        respuesta = cliente.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_DETECCION},
                {"role": "user", "content": f"Persona: {persona_nombre_completo}\nTitulo: {titulo}\nResumen: {texto}"},
            ],
            format="json",
            options={"temperature": 0},
        )
    except Exception as exc:
        # El motor local puede no estar disponible (Ollama caido, modelo no descargado, etc.);
        # el job diario no debe romperse por eso, simplemente se salta la deteccion.
        if lanzar_si_falla:
            raise ModeloNoDisponible(str(exc)) from exc
        return None

    try:
        datos = json.loads(respuesta.message.content)
    except (json.JSONDecodeError, TypeError):
        return None

    if not datos.get("es_caso"):
        return None
    if datos.get("tipo") not in {t.value for t in TipoCaso}:
        return None
    datos["tipo"] = ajustar_tipo(datos["tipo"], f"{titulo} {texto}")
    return datos


def procesar_articulos_pendientes(db: Session, limite: int = 50) -> int:
    """Recorre articulos sin procesar, busca menciones a personas ya registradas
    (por su nombre completo, su nombre comun o sus alias, sin importar tildes) y usa
    el modelo local para decidir si el articulo describe un caso real. Todo lo creado
    aqui queda con score bajo, por lo que requiere revision humana antes de
    considerarse verificado."""
    personas = db.scalars(select(Persona)).all()
    articulos = db.scalars(select(ArticuloRaw).where(ArticuloRaw.procesado.is_(False)).limit(limite)).all()

    casos_creados = 0
    for articulo in articulos:
        texto_articulo = f"{articulo.titulo} {articulo.contenido_texto}"

        for persona in personas:
            if not se_menciona(texto_articulo, persona):
                continue

            if es_solo_denunciante(texto_articulo, persona):
                continue

            nombre_completo = f"{persona.nombres} {persona.apellidos}"
            resultado = detectar_caso_en_texto(nombre_completo, articulo.titulo, articulo.contenido_texto)
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
                persona=persona,
            )
            casos_creados += 1

        articulo.procesado = True
        db.add(articulo)

    db.commit()
    return casos_creados
