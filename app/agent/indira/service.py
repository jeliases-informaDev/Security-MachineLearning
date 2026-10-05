import json
import uuid

from sqlalchemy.orm import Session

from app.agent.indira.llm_client import PROMPT_SISTEMA, generar_respuesta
from app.agent.indira.memoria import buscar_ejemplos_similares, construir_contexto_memoria
from app.agent.indira.tools import DEFINICIONES_HERRAMIENTAS, ejecutar_herramienta
from app.models.enums import CanalConversacion, EstadoConversacion, RolMensaje
from app.models.indira import ConversacionIndira, MensajeIndira

MAX_ITERACIONES_HERRAMIENTAS = 5


def obtener_o_crear_conversacion(
    db: Session, usuario_id: uuid.UUID, canal: CanalConversacion, conversacion_id: uuid.UUID | None
) -> ConversacionIndira:
    if conversacion_id is not None:
        conversacion = db.get(ConversacionIndira, conversacion_id)
        if conversacion is not None:
            return conversacion

    conversacion = ConversacionIndira(usuario_id=usuario_id, canal=canal, estado=EstadoConversacion.ACTIVA)
    db.add(conversacion)
    db.commit()
    db.refresh(conversacion)
    return conversacion


def _historial_para_llm(db: Session, conversacion: ConversacionIndira, mensaje_actual: str) -> list[dict]:
    mensajes = [{"role": "system", "content": PROMPT_SISTEMA}]

    contexto_memoria = construir_contexto_memoria(buscar_ejemplos_similares(db, mensaje_actual))
    if contexto_memoria:
        mensajes.append({"role": "system", "content": contexto_memoria})

    for m in sorted(conversacion.mensajes, key=lambda m: m.creado_en):
        mensajes.append({"role": m.rol.value, "content": m.contenido})
    return mensajes


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

    mensajes_llm = _historial_para_llm(db, conversacion, contenido)

    for _ in range(MAX_ITERACIONES_HERRAMIENTAS):
        mensaje_llm = generar_respuesta(mensajes_llm, herramientas=DEFINICIONES_HERRAMIENTAS)

        if not mensaje_llm.tool_calls:
            mensaje_final = MensajeIndira(
                conversacion_id=conversacion.id,
                rol=RolMensaje.ASSISTANT,
                contenido=mensaje_llm.content or "",
            )
            db.add(mensaje_final)
            db.commit()
            db.refresh(mensaje_final)
            return conversacion, mensaje_final

        mensajes_llm.append({"role": "assistant", "content": mensaje_llm.content or ""})

        for llamada in mensaje_llm.tool_calls:
            resultado = ejecutar_herramienta(
                db, usuario_id, llamada.function.name, dict(llamada.function.arguments)
            )
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
