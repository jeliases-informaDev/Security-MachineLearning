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
from app.schemas.persona import PersonaConCasosOut, PersonaListadoOut, PersonaOut

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


@router.get("", response_model=list[PersonaListadoOut])
def listar_personas(
    limite: int = Query(100, ge=1, le=1000, description="Maximo de personas a devolver"),
    es_pep: bool | None = Query(None, description="Filtra por persona expuesta politicamente"),
    con_casos: bool = Query(False, description="Incluye los casos no descartados de cada persona"),
    db: Session = Depends(get_db),
):
    """Lista las personas vigiladas (ordenadas por apellido). Lo usa la carga de Listas Negativas del backend."""
    consulta = select(Persona).order_by(Persona.apellidos, Persona.nombres).limit(limite)
    if es_pep is not None:
        consulta = consulta.where(Persona.es_pep.is_(es_pep))
    personas = db.scalars(consulta).all()

    casos_por_persona: dict[uuid.UUID, list[Caso]] = {}
    if con_casos and personas:
        casos = db.scalars(
            select(Caso)
            .where(Caso.persona_id.in_([p.id for p in personas]), Caso.estado_revision != EstadoRevision.DESCARTADO)
            .order_by(Caso.creado_en.desc())
        ).all()
        for caso in casos:
            casos_por_persona.setdefault(caso.persona_id, []).append(caso)

    return [
        PersonaListadoOut(
            **PersonaOut.model_validate(p).model_dump(),
            casos=[CasoOut.model_validate(c) for c in casos_por_persona.get(p.id, [])],
        )
        for p in personas
    ]


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
