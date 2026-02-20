from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import WasteAlert, CloudAccount
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_account_ids(db: Session, user_id: str) -> list:
    """Get all account IDs for a user."""
    accounts = (
        db.query(CloudAccount.id)
        .filter(CloudAccount.user_id == user_id)
        .all()
    )
    return [a[0] for a in accounts]


@router.get("/waste", response_class=HTMLResponse)
async def list_waste(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, str(user.id))

    alerts = (
        db.query(WasteAlert)
        .filter(WasteAlert.account_id.in_(account_ids))
        .order_by(WasteAlert.created_at.desc())
        .all()
    ) if account_ids else []

    open_count = sum(1 for a in alerts if a.status == "open")
    total_waste = sum(a.estimated_monthly_waste or 0 for a in alerts if a.status == "open")

    return templates.TemplateResponse(
        "waste/list.html",
        {
            "request": request,
            "user": user,
            "alerts": alerts,
            "open_count": open_count,
            "total_waste": total_waste,
        },
    )


@router.post("/waste/{id}/resolve")
async def resolve_waste(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    alert = db.query(WasteAlert).filter(WasteAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Verify ownership through account
    account = (
        db.query(CloudAccount)
        .filter(
            CloudAccount.id == alert.account_id,
            CloudAccount.user_id == str(user.id),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    db.commit()
    return RedirectResponse(url="/waste", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/waste/{id}/dismiss")
async def dismiss_waste(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    alert = db.query(WasteAlert).filter(WasteAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Verify ownership through account
    account = (
        db.query(CloudAccount)
        .filter(
            CloudAccount.id == alert.account_id,
            CloudAccount.user_id == str(user.id),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "dismissed"
    db.commit()
    return RedirectResponse(url="/waste", status_code=status.HTTP_303_SEE_OTHER)
