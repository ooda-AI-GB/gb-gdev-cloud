from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CloudResource, CloudAccount
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/resources", response_class=HTMLResponse)
async def list_resources(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    # Get all accounts for this user, then all resources across those accounts
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .all()
    )
    account_ids = [a.id for a in accounts]

    resources = (
        db.query(CloudResource)
        .filter(CloudResource.account_id.in_(account_ids))
        .order_by(CloudResource.created_at.desc())
        .all()
    ) if account_ids else []

    # Build account lookup for display
    account_map = {a.id: a for a in accounts}

    return templates.TemplateResponse(
        "resources/list.html",
        {
            "request": request,
            "user": user,
            "resources": resources,
            "account_map": account_map,
        },
    )


@router.get("/resources/{id}", response_class=HTMLResponse)
async def resource_detail(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    resource = db.query(CloudResource).filter(CloudResource.id == id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Verify ownership through account
    account = (
        db.query(CloudAccount)
        .filter(
            CloudAccount.id == resource.account_id,
            CloudAccount.user_id == str(user.id),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Resource not found")

    return templates.TemplateResponse(
        "resources/detail.html",
        {
            "request": request,
            "user": user,
            "resource": resource,
            "account": account,
        },
    )
