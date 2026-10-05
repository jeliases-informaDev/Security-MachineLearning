import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import CreadoPorTicket
from app.models.ticket import MensajeTicket, Ticket
from app.schemas.ticket import MensajeTicketCreate, MensajeTicketOut, TicketCreate, TicketOut

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=201)
def crear_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(**payload.model_dump(), creado_por=CreadoPorTicket.USUARIO)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketOut)
def obtener_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket


@router.get("/{ticket_id}/mensajes", response_model=list[MensajeTicketOut])
def listar_mensajes(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    mensajes = db.scalars(
        select(MensajeTicket).where(MensajeTicket.ticket_id == ticket_id).order_by(MensajeTicket.creado_en)
    ).all()
    return mensajes


@router.post("/{ticket_id}/mensajes", response_model=MensajeTicketOut, status_code=201)
def agregar_mensaje(ticket_id: uuid.UUID, payload: MensajeTicketCreate, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    mensaje = MensajeTicket(ticket_id=ticket_id, **payload.model_dump())
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)
    return mensaje
