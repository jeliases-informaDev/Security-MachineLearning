from app.models.articulo import ArticuloRaw
from app.models.caso import Caso
from app.models.fuente import Fuente
from app.models.indira import ConversacionIndira, EjemploVerificado, MensajeIndira, ReporteGenerado
from app.models.persona import Persona
from app.models.ticket import MensajeTicket, Ticket

__all__ = [
    "ArticuloRaw",
    "Caso",
    "Fuente",
    "ConversacionIndira",
    "EjemploVerificado",
    "MensajeIndira",
    "ReporteGenerado",
    "Persona",
    "MensajeTicket",
    "Ticket",
]
