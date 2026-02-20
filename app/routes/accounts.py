from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CloudAccount
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/accounts", response_class=HTMLResponse)
async def list_accounts(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .order_by(CloudAccount.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "accounts/list.html",
        {
            "request": request,
            "user": user,
            "accounts": accounts,
        },
    )


@router.get("/accounts/new", response_class=HTMLResponse)
async def new_account_form(
    request: Request,
    user: Any = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "accounts/form.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.post("/accounts/new")
async def create_account(
    request: Request,
    account_name: str = Form(...),
    provider: str = Form(...),
    account_id: str = Form(""),
    region: str = Form(""),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    account = CloudAccount(
        user_id=str(user.id),
        name=account_name,
        provider=provider,
        account_id=account_id or "unknown",
        region=region or None,
    )
    db.add(account)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/accounts/{id}/delete")
async def delete_account(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    account = (
        db.query(CloudAccount)
        .filter(
            CloudAccount.id == id,
            CloudAccount.user_id == str(user.id),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(account)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)
