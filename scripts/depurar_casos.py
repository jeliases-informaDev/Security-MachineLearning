"""Reaplica las guardas actuales a los casos automáticos que siguen pendientes de revisión.

Sirve cuando se mejoran los filtros y hay que limpiar lo que ya se había guardado con los
filtros anteriores.

Uso (desde la raíz del proyecto):
  venv/Scripts/python.exe -m scripts.depurar_casos            # solo muestra qué haría
  venv/Scripts/python.exe -m scripts.depurar_casos --aplicar  # lo hace

Los casos que no pasan las guardas se marcan "descartado": no se borran, quedan como registro
y la vigilancia no los vuelve a crear. Los casos verificados por una persona no se tocan.
"""

import argparse

from sqlalchemy import select

from app.core.database import SessionLocal
from app.ml_engine.deteccion_casos import SCORE_CONFIANZA_AUTOMATICA, ajustar_tipo, motivo_de_descarte
from app.models.caso import Caso
from app.models.enums import EstadoRevision, TipoCaso


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="aplica los cambios (por defecto solo los muestra)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        casos = db.scalars(
            select(Caso).where(
                Caso.estado_revision == EstadoRevision.PENDIENTE,
                Caso.score_confianza == SCORE_CONFIANZA_AUTOMATICA,
            )
        ).all()

        descartados = 0
        retipados = 0
        for caso in casos:
            persona, articulo = caso.persona, caso.articulo
            nombre = f"{persona.nombres} {persona.apellidos}"

            motivo = motivo_de_descarte(articulo.titulo, articulo.contenido_texto, persona)
            if motivo:
                print(f"DESCARTAR  {nombre}: {articulo.titulo[:90]}\n           -> {motivo}")
                descartados += 1
                if args.aplicar:
                    caso.estado_revision = EstadoRevision.DESCARTADO
                continue

            nuevo_tipo = ajustar_tipo(caso.tipo.value, f"{articulo.titulo} {articulo.contenido_texto}")
            if nuevo_tipo != caso.tipo.value:
                print(f"RETIPAR    {nombre}: {caso.tipo.value} -> {nuevo_tipo}: {articulo.titulo[:80]}")
                retipados += 1
                if args.aplicar:
                    caso.tipo = TipoCaso(nuevo_tipo)

        if args.aplicar:
            db.commit()

        accion = "aplicado" if args.aplicar else "(simulación; usa --aplicar para hacerlo)"
        print(f"\n{len(casos)} casos pendientes revisados: {descartados} descartados, {retipados} con tipo corregido {accion}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
