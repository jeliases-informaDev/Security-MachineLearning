import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.caso import Caso
from app.models.persona import Persona
from app.schemas.caso import CasoOut
from app.schemas.persona import PersonaOut

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


@router.get("/{persona_id}", response_model=PersonaOut)
def obtener_persona(persona_id: uuid.UUID, db: Session = Depends(get_db)):
    persona = db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return persona


@router.get("/{persona_id}/casos", response_model=list[CasoOut])
def listar_casos_de_persona(persona_id: uuid.UUID, db: Session = Depends(get_db)):
    persona = db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    casos = db.scalars(
        select(Caso).where(Caso.persona_id == persona_id).order_by(Caso.creado_en.desc())
    ).all()
    return casos
