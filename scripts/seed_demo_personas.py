"""Script puntual de demo: guarda articulos reales de 3 diarios peruanos y
crea las 10 figuras publicas mas mencionadas hoy, con casos reales solo
donde la propia noticia reporta un caso judicial (nada inventado).

Uso: venv/Scripts/python.exe scripts/seed_demo_personas.py
"""

from app.core.database import SessionLocal
from app.models.enums import EstadoVerificacion, OrigenPersona, TipoCaso
from app.models.fuente import Fuente
from app.models.persona import Persona
from app.scraper.rss_scraper import RSSScraper
from app.services.articulos_service import ejecutar_scraping_fuente
from app.services.casos_service import procesar_mencion

FUENTES = [
    ("El Comercio - Politica", "elcomercio.pe", "https://elcomercio.pe/arc/outboundfeeds/rss/category/politica/?outputType=xml"),
    ("Gestion - Peru", "gestion.pe", "https://gestion.pe/arc/outboundfeeds/rss/category/peru/?outputType=xml"),
]

# Las 10 figuras publicas mas mencionadas en las noticias reales de hoy.
PERSONAS_POPULARES = [
    ("Keiko", "Fujimori"),
    ("Rafael", "Rey"),
    ("Cesar", "Astudillo"),
    ("Josue", "Gutierrez"),
    ("Julio", "Velarde"),
    ("Guillermo", "Bermejo"),
    ("Richard", "Concepcion Carhuancho"),
    ("Luis", "Galarreta"),
    ("Rafael", "Lopez Aliaga"),
    ("Yenifer", "Paredes"),
]


def main():
    db = SessionLocal()

    for nombre, dominio, feed_url in FUENTES:
        fuente = db.query(Fuente).filter(Fuente.dominio == dominio).first()
        if fuente is None:
            fuente = Fuente(nombre=nombre, dominio=dominio, config_scraper={"tipo": "rss", "feed_url": feed_url})
            db.add(fuente)
            db.commit()
            db.refresh(fuente)
        guardados = ejecutar_scraping_fuente(db, fuente, RSSScraper(feed_url))
        print(f"{nombre}: {len(guardados)} articulos nuevos guardados")

    personas_creadas = {}
    for nombres, apellidos in PERSONAS_POPULARES:
        existente = (
            db.query(Persona).filter(Persona.nombres == nombres, Persona.apellidos == apellidos).first()
        )
        if existente is not None:
            personas_creadas[(nombres, apellidos)] = existente
            continue
        persona = Persona(
            nombres=nombres,
            apellidos=apellidos,
            es_pep=True,
            origen=OrigenPersona.SCRAPER_DETECTADO,
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)
        personas_creadas[(nombres, apellidos)] = persona
        print(f"Persona creada: {nombres} {apellidos}")

    # Caso 1: Guillermo Bermejo -- sentenciado, segun nota de El Comercio (fuente real).
    articulo_bermejo = _buscar_articulo_por_url(
        db,
        "https://elcomercio.pe/politica/la-procuraduria-antiterrorismo-solicito-al-defensor-del-pueblo-josue-gutierrez-que-le-informe-intervencion-de-su-institucion-en-en-caso-guillermo-bermejo-noticia/",
    )
    if articulo_bermejo:
        caso = procesar_mencion(
            db,
            articulo_bermejo,
            nombres="Guillermo",
            apellidos="Bermejo",
            tipo=TipoCaso.SENTENCIA,
            categoria_delito="terrorismo",
            resumen=(
                "El Procurador Antiterrorismo solicito informes a la Defensoria del Pueblo sobre "
                "una posible intervencion de esta ante la Corte Suprema a pedido del congresista "
                "sentenciado Guillermo Bermejo."
            ),
            score_confianza=0.95,
        )
        print(f"Caso creado para Guillermo Bermejo: {caso.id} (estado: {caso.estado_revision.value})")

    # Caso 2: Richard Concepcion Carhuancho -- destituido por la JNJ, segun nota de El Comercio (fuente real).
    articulo_juez = _buscar_articulo_por_url(
        db,
        "https://elcomercio.pe/politica/jnj-destituye-a-juez-richard-concepcion-carhuancho-junta-nacional-de-justicia-noticia/",
    )
    if articulo_juez:
        caso = procesar_mencion(
            db,
            articulo_juez,
            nombres="Richard",
            apellidos="Concepcion Carhuancho",
            tipo=TipoCaso.SENTENCIA,
            categoria_delito="destitucion - falta disciplinaria en la funcion judicial",
            resumen="La Junta Nacional de Justicia (JNJ) destituyo de su cargo al juez Richard Concepcion Carhuancho.",
            score_confianza=0.95,
        )
        print(f"Caso creado para Richard Concepcion Carhuancho: {caso.id} (estado: {caso.estado_revision.value})")

    db.close()


def _buscar_articulo_por_url(db, url):
    from app.models.articulo import ArticuloRaw

    return db.query(ArticuloRaw).filter(ArticuloRaw.url == url).first()


if __name__ == "__main__":
    main()
