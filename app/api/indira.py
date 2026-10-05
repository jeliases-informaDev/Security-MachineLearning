import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.indira.feedback_service import registrar_feedback
from app.agent.indira.service import enviar_mensaje
from app.core.database import get_db
from app.schemas.indira import FeedbackRequest, IndiraChatRequest, IndiraChatResponse

router = APIRouter(prefix="/api/v1/indira", tags=["indira"])


@router.post("/chat", response_model=IndiraChatResponse)
def chat(payload: IndiraChatRequest, db: Session = Depends(get_db)):
    conversacion, mensaje = enviar_mensaje(
        db,
        usuario_id=payload.usuario_id,
        canal=payload.canal,
        contenido=payload.mensaje,
        conversacion_id=payload.conversacion_id,
    )
    return IndiraChatResponse(conversacion_id=conversacion.id, mensaje_id=mensaje.id, respuesta=mensaje.contenido)


@router.post("/mensajes/{mensaje_id}/feedback")
def enviar_feedback(mensaje_id: uuid.UUID, payload: FeedbackRequest, db: Session = Depends(get_db)):
    try:
        mensaje = registrar_feedback(db, mensaje_id, payload.feedback)
    except ValueError:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return {"mensaje_id": str(mensaje.id), "feedback": mensaje.feedback.value}
