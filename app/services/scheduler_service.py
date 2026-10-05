from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.database import SessionLocal
from app.ml_engine.deteccion_casos import procesar_articulos_pendientes
from app.models.fuente import Fuente
from app.scraper.rss_scraper import RSSScraper
from app.services.articulos_service import ejecutar_scraping_fuente

scheduler = BackgroundScheduler()


def job_scraping_diario() -> None:
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
        print(f"[scheduler] {casos_creados} casos nuevos detectados (pendientes de revision)")
    finally:
        db.close()


def iniciar_scheduler() -> None:
    scheduler.add_job(job_scraping_diario, CronTrigger(hour=6, minute=0), id="scraping_diario", replace_existing=True)
    scheduler.start()


def detener_scheduler() -> None:
    scheduler.shutdown(wait=False)
