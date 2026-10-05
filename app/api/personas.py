import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml_engine.matching import buscar_persona_por_texto
from app.models.caso import Caso
from app.models.enums import EstadoRevision
from app.models.persona import Persona
from app.schemas.caso import CasoOut
from app.schemas.persona import PersonaConCasosOut, PersonaOut

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


@router.get("/buscar", response_model=PersonaConCasosOut)
def buscar_persona(q: str = Query(min_length=3, description="Nombre o número de documento"), db: Session = Depends(get_db)):
    # Se declara antes que "/{persona_id}" para que "buscar" no se interprete como un UUID.
    persona = buscar_persona_por_texto(db, q)
    if persona is None:
        return PersonaConCasosOut(persona=None, casos=[])

    casos = db.scalars(
        select(Caso)
        .where(Caso.persona_id == persona.id, Caso.estado_revision != EstadoRevision.DESCARTADO)
        .order_by(Caso.creado_en.desc())
    ).all()
    return PersonaConCasosOut(persona=persona, casos=casos)


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
        select(Caso)
        .where(Caso.persona_id == persona_id, Caso.estado_revision != EstadoRevision.DESCARTADO)
        .order_by(Caso.creado_en.desc())
    ).all()
    return casos
