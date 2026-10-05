import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml_engine.matching import buscar_persona_por_texto
from app.models.caso import Caso
from app.models.enums import CanalTicket, CreadoPorTicket, EstadoTicket, PrioridadTicket, TipoTicket
from app.models.ticket import MensajeTicket, Ticket

# Definición de herramientas en formato OpenAI/Ollama tool-calling.
DEFINICIONES_HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_persona",
            "description": (
                "Busca una persona por nombre completo o número de documento y devuelve "
                "su información de riesgo y los casos/acusaciones registrados sobre ella."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_o_documento": {
                        "type": "string",
                        "description": "Nombre completo de la persona o su número de documento",
                    }
                },
                "required": ["nombre_o_documento"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_ticket",
            "description": (
                "Crea un ticket de soporte/reporte/reclamo a nombre del usuario cuando la "
                "conversación lo requiere (un problema, una queja o un reporte formal)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": [t.value for t in TipoTicket],
                        "description": "Tipo de ticket",
                    },
                    "asunto": {"type": "string", "description": "Resumen corto del asunto"},
                    "descripcion": {"type": "string", "description": "Detalle del problema o solicitud"},
                },
                "required": ["tipo", "asunto", "descripcion"],
            },
        },
    },
]


MAX_CASOS_EN_RESPUESTA = 8


def consultar_persona(db: Session, nombre_o_documento: str) -> dict:
    persona = buscar_persona_por_texto(db, nombre_o_documento)
    if persona is None:
        return {"encontrado": False, "mensaje": "No se encontró ninguna persona que coincida con esa búsqueda."}

    # Los más recientes primero y con un tope: más de eso satura el contexto del modelo.
    casos = db.scalars(
        select(Caso).where(Caso.persona_id == persona.id).order_by(Caso.creado_en.desc()).limit(MAX_CASOS_EN_RESPUESTA)
    ).all()

    return {
        "encontrado": True,
        "persona": {
            "id": str(persona.id),
            "nombres": persona.nombres,
            "apellidos": persona.apellidos,
            "es_pep": persona.es_pep,
            "nivel_riesgo_score": persona.nivel_riesgo_score,
            "estado_verificacion": persona.estado_verificacion.value,
        },
        "casos": [
            {
                "tipo": caso.tipo.value,
                "categoria_delito": caso.categoria_delito,
                "resumen": caso.resumen,
                "url_fuente": caso.url_fuente,
                "diario": caso.articulo.fuente.nombre,
                "fecha_publicacion": caso.articulo.fecha_publicacion.isoformat() if caso.articulo.fecha_publicacion else None,
                "estado_revision": caso.estado_revision.value,
            }
            for caso in casos
        ],
    }


def crear_ticket(db: Session, usuario_id: uuid.UUID, tipo: str, asunto: str, descripcion: str) -> dict:
    ticket = Ticket(
        usuario_id=usuario_id,
        canal=CanalTicket.CHAT_INDIRA,
        tipo=TipoTicket(tipo),
        asunto=asunto,
        estado=EstadoTicket.ABIERTO,
        prioridad=PrioridadTicket.MEDIA,
        creado_por=CreadoPorTicket.INDIRA,
    )
    db.add(ticket)
    db.flush()

    db.add(MensajeTicket(ticket_id=ticket.id, autor="indira", contenido=descripcion))
    db.commit()

    return {"ticket_id": str(ticket.id), "estado": ticket.estado.value, "mensaje": "Ticket creado correctamente."}


def ejecutar_herramienta(db: Session, usuario_id: uuid.UUID, nombre: str, argumentos: dict) -> dict:
    try:
        if nombre == "consultar_persona":
            return consultar_persona(db, **argumentos)
        if nombre == "crear_ticket":
            return crear_ticket(db, usuario_id=usuario_id, **argumentos)
        return {"error": f"Herramienta desconocida: {nombre}"}
    except (TypeError, ValueError) as exc:
        # El LLM puede generar argumentos mal formados; esto no debe tumbar la conversación.
        return {"error": f"Argumentos inválidos para '{nombre}': {exc}"}
