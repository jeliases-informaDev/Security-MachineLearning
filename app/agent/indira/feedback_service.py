import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FeedbackMensaje, RolMensaje
from app.models.indira import EjemploVerificado, MensajeIndira


def _mensaje_usuario_anterior(db: Session, mensaje: MensajeIndira) -> MensajeIndira | None:
    return db.scalar(
        select(MensajeIndira)
        .where(
            MensajeIndira.conversacion_id == mensaje.conversacion_id,
            MensajeIndira.rol == RolMensaje.USER,
            MensajeIndira.creado_en < mensaje.creado_en,
        )
        .order_by(MensajeIndira.creado_en.desc())
    )


def registrar_feedback(db: Session, mensaje_id: uuid.UUID, feedback: FeedbackMensaje) -> MensajeIndira:
    mensaje = db.get(MensajeIndira, mensaje_id)
    if mensaje is None:
        raise ValueError(f"Mensaje no encontrado: {mensaje_id}")

    mensaje.feedback = feedback

    ejemplo_existente = db.scalar(
        select(EjemploVerificado).where(EjemploVerificado.mensaje_origen_id == mensaje_id)
    )

    if feedback == FeedbackMensaje.POSITIVO and ejemplo_existente is None:
        pregunta = _mensaje_usuario_anterior(db, mensaje)
        if pregunta is not None:
            db.add(
                EjemploVerificado(
                    mensaje_origen_id=mensaje.id,
                    pregunta_usuario=pregunta.contenido,
                    respuesta_indira=mensaje.contenido,
                )
            )
    elif feedback == FeedbackMensaje.NEGATIVO and ejemplo_existente is not None:
        db.delete(ejemplo_existente)

    db.commit()
    db.refresh(mensaje)
    return mensaje
