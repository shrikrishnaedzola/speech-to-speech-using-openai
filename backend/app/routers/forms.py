"""GET /api/forms and GET /api/forms/{id}."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Form
from ..services.forms import load_form

router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.get("")
def list_forms(db: Session = Depends(get_db)):
    return [{"id": f.id, "name": f.name} for f in db.scalars(select(Form).order_by(Form.name))]


@router.get("/{form_id}")
def get_form(form_id: str, db: Session = Depends(get_db)):
    form = load_form(db, form_id)
    if form is None:
        raise HTTPException(404, "Form not found")
    return form
