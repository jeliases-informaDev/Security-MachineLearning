import uuid

from sqlalchemy.orm import Session

from app.models.enums import FeedbackMensaje
from app.models.indira import MensajeIndira


def registrar_feedback(
    db: Session, mensaje_id: uuid.UUID, feedback: FeedbackMensaje, usuario_id: uuid.UUID | None = None
) -> MensajeIndira:
    """Guarda la marca en el mensaje. Ya no crea ejemplos: esa tabla no tiene empresa y mezclaba a los clientes.

    `usuario_id` es opcional mientras haya un backend que no lo envia. Si llega y no es el dueno,
    responde igual que un mensaje inexistente.
    """
    mensaje = db.get(MensajeIndira, mensaje_id)
    if mensaje is None or (usuario_id is not None and mensaje.conversacion.usuario_id != usuario_id):
        raise ValueError(f"Mensaje no encontrado: {mensaje_id}")

    mensaje.feedback = feedback
    db.commit()
    db.refresh(mensaje)
    return mensaje
