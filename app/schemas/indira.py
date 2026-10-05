import uuid

from pydantic import BaseModel

from app.models.enums import CanalConversacion, FeedbackMensaje


class IndiraChatRequest(BaseModel):
    usuario_id: uuid.UUID
    canal: CanalConversacion
    mensaje: str
    conversacion_id: uuid.UUID | None = None


class IndiraChatResponse(BaseModel):
    conversacion_id: uuid.UUID
    mensaje_id: uuid.UUID
    respuesta: str


class FeedbackRequest(BaseModel):
    feedback: FeedbackMensaje
