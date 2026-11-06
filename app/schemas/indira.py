import uuid

from pydantic import BaseModel, Field

from app.models.enums import CanalConversacion, FeedbackMensaje


class IndiraChatRequest(BaseModel):
    usuario_id: uuid.UUID
    canal: CanalConversacion
    mensaje: str = Field(max_length=2000)
    conversacion_id: uuid.UUID | None = None


class IndiraChatResponse(BaseModel):
    conversacion_id: uuid.UUID
    mensaje_id: uuid.UUID
    respuesta: str


class FeedbackRequest(BaseModel):
    feedback: FeedbackMensaje
    # Opcional mientras haya un backend que no lo envia. Si llega, se exige que sea el dueno del mensaje.
    usuario_id: uuid.UUID | None = None
