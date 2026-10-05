import traceback
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.ml_engine.deteccion_casos import procesar_articulos_pendientes
from app.models.articulo import ArticuloRaw
from app.models.fuente import Fuente
from app.scraper.rss_scraper import RSSScraper
from app.services.articulos_service import ejecutar_scraping_fuente
from app.services.vigilancia_service import VigilanciaEnCurso, ejecutar_vigilancia_en_sesion

scheduler = BackgroundScheduler(timezone=settings.ZONA_HORARIA)

# Si la última corrida fue hace más que esto, al encender el servicio se corre una de inmediato.
HORAS_SIN_CORRER_PARA_ACTUALIZAR = 20


def _paso_rss() -> None:
    """Últimas notas de los RSS de los diarios y menciones de personas ya registradas."""
    db = SessionLocal()
    try:
        fuentes = db.scalars(select(Fuente).where(Fuente.activo.is_(True))).all()
        for fuente in fuentes:
            config = fuente.config_scraper or {}
            if config.get("tipo") != "rss" or not config.get("feed_url"):
                continue
            guardados = ejecutar_scraping_fuente(db, fuente, RSSScraper(config["feed_url"]))
            print(f"[scheduler] {fuente.nombre}: {len(guardados)} articulos nuevos")

        casos_creados = procesar_articulos_pendientes(db)
        print(f"[scheduler] {casos_creados} casos nuevos detectados en los RSS (pendientes de revision)")
    finally:
        db.close()


def _paso_vigilancia() -> None:
    """Búsqueda por persona en la prensa nacional (ver vigilancia_service)."""
    try:
        resultado = ejecutar_vigilancia_en_sesion(
            dias=settings.VIGILANCIA_DIAS,
            max_por_persona=settings.VIGILANCIA_MAX_POR_PERSONA,
            log=lambda linea: print(f"[vigilancia]{linea}"),
        )
        print(
            f"[scheduler] vigilancia: {resultado.personas_revisadas} personas, "
            f"{resultado.articulos_nuevos} articulos nuevos, {resultado.casos_creados} casos nuevos"
        )
    except VigilanciaEnCurso:
        print("[scheduler] ya hay una vigilancia en curso; se omite esta corrida")


def job_scraping_diario() -> None:
    # Cada paso es independiente: si falla uno (un diario caído, Ollama apagado), el otro igual corre.
    for paso in (_paso_rss, _paso_vigilancia):
        try:
            paso()
        except Exception:
            print(f"[scheduler] error en {paso.__name__}:\n{traceback.format_exc()}")


def ultimo_scrapeo() -> datetime | None:
    db = SessionLocal()
    try:
        return db.scalar(select(func.max(ArticuloRaw.fecha_scrapeo)))
    finally:
        db.close()


def hace_falta_actualizar() -> bool:
    try:
        ultimo = ultimo_scrapeo()
    except Exception:
        # Sin base de datos no hay nada que decidir; el servicio igual debe poder arrancar.
        print(f"[scheduler] no se pudo consultar el ultimo scrapeo:\n{traceback.format_exc()}")
        return False
    if ultimo is None:
        return True
    return datetime.now(timezone.utc) - ultimo > timedelta(hours=HORAS_SIN_CORRER_PARA_ACTUALIZAR)


def ejecutar_ahora() -> None:
    """Programa una corrida inmediata en segundo plano (no bloquea al que la pide)."""
    scheduler.add_job(job_scraping_diario, id="scraping_manual", replace_existing=True, max_instances=1)


def iniciar_scheduler() -> None:
    scheduler.add_job(
        job_scraping_diario,
        CronTrigger(hour=settings.SCRAPING_HORA, minute=0, timezone=settings.ZONA_HORARIA),
        id="scraping_diario",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()

    if settings.SCRAPING_AL_ARRANCAR and hace_falta_actualizar():
        print("[scheduler] la ultima corrida fue hace mas de un dia: se ejecuta una ahora")
        ejecutar_ahora()


def detener_scheduler() -> None:
    scheduler.shutdown(wait=False)
