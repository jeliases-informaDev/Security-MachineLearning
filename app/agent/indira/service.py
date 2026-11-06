import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.indira.fuentes import agregar_fuentes
from app.agent.indira.llm_client import PROMPT_SISTEMA, ModeloNoDisponible, generar_respuesta
from app.agent.indira.tools import DEFINICIONES_HERRAMIENTAS, ejecutar_herramienta
from app.core.config import settings
from app.models.enums import CanalConversacion, EstadoConversacion, RolMensaje
from app.models.indira import ConversacionIndira, MensajeIndira

MAX_ITERACIONES_HERRAMIENTAS = 5


class ConversacionNoEncontrada(Exception):
    """El id no existe o es de otro usuario. Son el mismo error a proposito: asi la
    respuesta no revela si una conversacion ajena existe."""


def obtener_o_crear_conversacion(
    db: Session, usuario_id: uuid.UUID, canal: CanalConversacion, conversacion_id: uuid.UUID | None
) -> ConversacionIndira:
    if conversacion_id is not None:
        conversacion = db.scalar(
            select(ConversacionIndira).where(
                ConversacionIndira.id == conversacion_id,
                ConversacionIndira.usuario_id == usuario_id,
            )
        )
        if conversacion is None:
            raise ConversacionNoEncontrada(str(conversacion_id))
        return conversacion

    conversacion = ConversacionIndira(usuario_id=usuario_id, canal=canal, estado=EstadoConversacion.ACTIVA)
    db.add(conversacion)
    db.commit()
    db.refresh(conversacion)
    return conversacion


def _historial_para_llm(db: Session, conversacion: ConversacionIndira) -> list[dict]:
    recientes = db.scalars(
        select(MensajeIndira)
        .where(MensajeIndira.conversacion_id == conversacion.id)
        .order_by(MensajeIndira.creado_en.desc())
        .limit(settings.INDIRA_VENTANA_HISTORIAL)
    ).all()
    ventana = list(reversed(recientes))

    # La ventana puede cortar entre una pregunta y su respuesta: no se empieza por una respuesta suelta.
    while len(ventana) > 1 and ventana[0].rol != RolMensaje.USER:
        ventana.pop(0)

    mensajes = [{"role": "system", "content": PROMPT_SISTEMA}]
    mensajes.extend({"role": m.rol.value, "content": m.contenido} for m in ventana)
    return mensajes


def _llamadas_para_reenviar(tool_calls) -> list[dict]:
    """El modelo necesita ver su propia llamada junto al resultado; sin ella puede repetirla."""
    return [
        {"function": {"name": llamada.function.name, "arguments": dict(llamada.function.arguments)}}
        for llamada in tool_calls
    ]


def enviar_mensaje(
    db: Session,
    usuario_id: uuid.UUID,
    canal: CanalConversacion,
    contenido: str,
    conversacion_id: uuid.UUID | None = None,
) -> tuple[ConversacionIndira, MensajeIndira]:
    conversacion = obtener_o_crear_conversacion(db, usuario_id, canal, conversacion_id)

    db.add(MensajeIndira(conversacion_id=conversacion.id, rol=RolMensaje.USER, contenido=contenido))
    db.commit()
    db.refresh(conversacion)

    mensajes_llm = _historial_para_llm(db, conversacion)
    casos_consultados: list[dict] = []
    # Un solo plazo para todo el turno, no uno por pasada: el backend deja de esperar a un tiempo fijo.
    limite = time.monotonic() + settings.OLLAMA_TIMEOUT_SEGUNDOS

    for _ in range(MAX_ITERACIONES_HERRAMIENTAS):
        restante = limite - time.monotonic()
        if restante <= 0:
            raise ModeloNoDisponible("Se agoto el tiempo del turno")
        mensaje_llm = generar_respuesta(mensajes_llm, herramientas=DEFINICIONES_HERRAMIENTAS, timeout=restante)

        if not mensaje_llm.tool_calls:
            mensaje_final = MensajeIndira(
                conversacion_id=conversacion.id,
                rol=RolMensaje.ASSISTANT,
                contenido=agregar_fuentes(mensaje_llm.content or "", casos_consultados),
            )
            db.add(mensaje_final)
            db.commit()
            db.refresh(mensaje_final)
            return conversacion, mensaje_final

        mensajes_llm.append(
            {
                "role": "assistant",
                "content": mensaje_llm.content or "",
                "tool_calls": _llamadas_para_reenviar(mensaje_llm.tool_calls),
            }
        )

        for llamada in mensaje_llm.tool_calls:
            resultado = ejecutar_herramienta(
                db, usuario_id, llamada.function.name, dict(llamada.function.arguments)
            )
            if llamada.function.name == "consultar_persona" and resultado.get("encontrado"):
                casos_consultados.extend(resultado.get("casos", []))
            mensajes_llm.append(
                {"role": "tool", "content": json.dumps(resultado, ensure_ascii=False), "tool_name": llamada.function.name}
            )

    mensaje_final = MensajeIndira(
        conversacion_id=conversacion.id,
        rol=RolMensaje.ASSISTANT,
        contenido="No pude completar tu solicitud tras varios intentos con las herramientas disponibles.",
    )
    db.add(mensaje_final)
    db.commit()
    db.refresh(mensaje_final)
    return conversacion, mensaje_final
