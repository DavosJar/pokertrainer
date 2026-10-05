import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.scenario import Scenario

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates"
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def index_view(request: Request, db: Session = Depends(get_db)):
    scenarios = db.execute(select(Scenario)).scalars().all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"active_tab": "setup", "scenarios": scenarios}
    )


@router.get("/train", response_class=HTMLResponse)
def train_view(request: Request):
    return templates.TemplateResponse(
        request,
        "train.html",
        {"active_tab": "train"}
    )


@router.get("/stats", response_class=HTMLResponse)
def stats_view(request: Request):
    return templates.TemplateResponse(
        request,
        "stats.html",
        {"active_tab": "stats"}
    )


@router.get("/ranges", response_class=HTMLResponse)
def ranges_view(request: Request):
    return templates.TemplateResponse(
        request,
        "ranges.html",
        {"active_tab": "ranges"}
    )
