import ollama

from app.core.config import settings

PROMPT_SISTEMA = (
    "Eres Indira, la asistente de IA de la plataforma Security. Ayudas a los usuarios a "
    "consultar información sobre personas y casos registrados en la plataforma, y puedes "
    "crear tickets de soporte o reporte cuando lo necesiten. Responde siempre en español, "
    "de forma clara y profesional. Si no tienes la información para responder algo, dilo "
    "honestamente en vez de inventar."
)


def generar_respuesta(mensajes: list[dict], herramientas: list[dict] | None = None) -> ollama.Message:
    cliente = ollama.Client(host=settings.OLLAMA_BASE_URL)
    respuesta = cliente.chat(
        model=settings.OLLAMA_MODEL,
        messages=mensajes,
        tools=herramientas,
        # Temperatura baja: mas determinismo, mas confiabilidad al usar herramientas.
        options={"temperature": 0.2},
    )
    return respuesta.message
