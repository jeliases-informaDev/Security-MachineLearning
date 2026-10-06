"""Ejecuta la vigilancia de prensa ahora mismo (la misma que corre a diario).

Uso (desde la raíz del proyecto):
  venv/Scripts/python.exe -m scripts.ejecutar_vigilancia
  venv/Scripts/python.exe -m scripts.ejecutar_vigilancia --dias 90 --max 10
  venv/Scripts/python.exe -m scripts.ejecutar_vigilancia --persona Cerrón

Requiere Ollama corriendo con el modelo configurado. Los casos que encuentra quedan
pendientes de revisión, con el enlace directo a la nota del diario.
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.services.vigilancia_service import ejecutar_vigilancia


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dias", type=int, default=30, help="ventana de búsqueda en días (por defecto 30)")
    parser.add_argument("--max", type=int, default=6, help="máximo de noticias por persona (por defecto 6)")
    parser.add_argument("--persona", help="vigila solo a las personas cuyo nombre contiene este texto")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resultado = ejecutar_vigilancia(db, dias=args.dias, max_por_persona=args.max, solo=args.persona)
    finally:
        db.close()

    print()
    print(f"Personas revisadas : {resultado.personas_revisadas}")
    print(f"Noticias halladas  : {resultado.noticias_encontradas}")
    print(f"Candidatas         : {resultado.candidatas}")
    print(f"Artículos nuevos   : {resultado.articulos_nuevos}")
    print(f"Casos creados      : {resultado.casos_creados}")
    for error in resultado.errores:
        print(f"  ! {error}")
    return 0 if resultado.modelo_disponible else 1


if __name__ == "__main__":
    sys.exit(main())
