import httpx
import ollama

from app.core.config import settings

PROMPT_SISTEMA = (
    "Eres Indira, la asistente de IA de la plataforma Security. Ayudas a los usuarios a "
    "consultar información sobre personas y casos registrados en la plataforma, y puedes "
    "crear tickets de soporte o reporte cuando lo necesiten. Responde siempre en español, "
    "de forma clara y profesional. Si no tienes la información para responder algo, dilo "
    "honestamente en vez de inventar.\n\n"
    "Cuando presentes los casos de una persona:\n"
    "- Preséntalos como noticias de prensa detectadas automáticamente, es decir, como "
    "'reportados por el diario', nunca como hechos probados. Respeta la presunción de "
    "inocencia y no afirmes que alguien es culpable.\n"
    "- Si el 'estado_revision' de un caso es 'pendiente', aclara que todavía no lo ha "
    "verificado una persona del equipo.\n"
    "- Incluye siempre el enlace (url_fuente) de cada caso, copiado exactamente como lo "
    "devuelve la herramienta, y menciona el diario y la fecha cuando estén disponibles.\n"
    "- Usa solo los datos que devuelve la herramienta: no agregues casos, fechas, delitos ni "
    "cargos que no aparezcan en ellos."
)


class ModeloNoDisponible(Exception):
    """Ollama no respondio a tiempo o no esta disponible."""


def generar_respuesta(
    mensajes: list[dict], herramientas: list[dict] | None = None, timeout: float | None = None
) -> ollama.Message:
    cliente = ollama.Client(host=settings.OLLAMA_BASE_URL, timeout=timeout or settings.OLLAMA_TIMEOUT_SEGUNDOS)
    try:
        respuesta = cliente.chat(
            model=settings.OLLAMA_MODEL,
            messages=mensajes,
            tools=herramientas,
            # Temperatura baja: mas determinismo, mas confiabilidad al usar herramientas.
            options={"temperature": 0.2, "num_ctx": settings.OLLAMA_NUM_CTX},
        )
    except (httpx.HTTPError, ollama.ResponseError, ConnectionError) as exc:
        raise ModeloNoDisponible(str(exc)) from exc
    return respuesta.message
