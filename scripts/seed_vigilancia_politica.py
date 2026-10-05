"""Registra figuras de la política peruana para que la vigilancia diaria las siga en la prensa.

Uso (desde la raíz del proyecto): venv/Scripts/python.exe -m scripts.seed_vigilancia_politica

Solo se cargan NOMBRES de personas públicas. Ningún caso, acusación ni enlace se escribe
aquí: los casos los detecta la vigilancia a partir de notas reales de diarios nacionales y
quedan pendientes de revisión. Es seguro ejecutarlo varias veces (no duplica personas).
Para vigilar a alguien más, agrégalo a la lista.
"""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.ml_engine.nombres import variantes_nombre
from app.models.enums import EstadoVerificacion, OrigenPersona
from app.models.persona import Persona

# (nombres, apellidos, alias, es_pep)
# es_pep solo es True para quien ejerció un cargo público de alto nivel. Quien nunca lo
# ejerció (candidatos, familiares) igual se vigila, pero sin marcarlo como PEP.
FIGURAS_POLITICAS = [
    # Presidentes y expresidentes
    ("Dina", "Boluarte", [], True),
    ("Pedro", "Castillo", [], True),
    ("Martín", "Vizcarra", [], True),
    ("Pedro Pablo", "Kuczynski", ["PPK"], True),
    ("Ollanta", "Humala", [], True),
    ("Alejandro", "Toledo", [], True),
    ("Manuel", "Merino", [], True),
    ("Francisco", "Sagasti", [], True),
    # Presidentes del Consejo de Ministros, ministros y congresistas
    ("Alberto", "Otárola", [], True),
    ("Betssy", "Chávez", [], True),
    ("Aníbal", "Torres", [], True),
    ("Mirtha", "Vásquez", [], True),
    ("Guido", "Bellido", [], True),
    ("Fernando", "Rospigliosi", [], True),
    ("Daniel", "Urresti", [], True),
    ("Verónika", "Mendoza", [], True),
    ("George", "Forsyth", [], True),
    # Autoridades regionales y municipales
    ("Vladimir", "Cerrón", [], True),
    ("César", "Acuña", [], True),
    ("Gregorio", "Santos", [], True),
    ("Susana", "Villarán", [], True),
    ("Renzo", "Reggiardo", [], True),
    # Fiscales de la Nación
    ("Patricia", "Benavides", [], True),
    ("Zoraida", "Ávalos", [], True),
    ("Delia", "Espinoza", [], True),
    # Figuras políticas sin cargo de alto nivel (candidatos, familiares): se vigilan, no son PEP
    ("Nadine", "Heredia", [], False),
    ("Antauro", "Humala", [], False),
    ("Julio", "Guzmán", [], False),
    ("Hernando", "de Soto", [], False),
]


def main():
    db = SessionLocal()
    try:
        existentes = db.scalars(select(Persona)).all()
        ya_registradas = {v for p in existentes for v in variantes_nombre(p)}

        creadas = 0
        for nombres, apellidos, alias, es_pep in FIGURAS_POLITICAS:
            candidata = Persona(
                nombres=nombres,
                apellidos=apellidos,
                nombres_alternativos=alias,
                es_pep=es_pep,
                origen=OrigenPersona.SCRAPER_DETECTADO,
                estado_verificacion=EstadoVerificacion.VERIFICADO,
            )
            # Se considera repetida si comparte nombre completo o nombre común con alguien ya registrado.
            if ya_registradas & set(variantes_nombre(candidata)[:2]):
                continue
            db.add(candidata)
            ya_registradas.update(variantes_nombre(candidata))
            creadas += 1

        db.commit()
        total = db.query(Persona).count()
        print(f"Personas nuevas: {creadas}. Total vigiladas: {total}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
