from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Budget, CloudAccount
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/budgets", response_class=HTMLResponse)
async def list_budgets(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    budgets = (
        db.query(Budget)
        .filter(Budget.user_id == str(user.id))
        .order_by(Budget.created_at.desc())
        .all()
    )

    # Get accounts for display
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .all()
    )
    account_map = {a.id: a for a in accounts}

    return templates.TemplateResponse(
        "budgets/list.html",
        {
            "request": request,
            "user": user,
            "budgets": budgets,
            "account_map": account_map,
        },
    )


@router.get("/budgets/new", response_class=HTMLResponse)
async def new_budget_form(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .all()
    )
    return templates.TemplateResponse(
        "budgets/form.html",
        {
            "request": request,
            "user": user,
            "accounts": accounts,
        },
    )


@router.post("/budgets/new")
async def create_budget(
    request: Request,
    name: str = Form(...),
    monthly_limit: float = Form(...),
    alert_threshold_percent: float = Form(80.0),
    period_start: str = Form(""),
    account_id: int = Form(None),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    # If account_id provided, verify ownership
    if account_id:
        account = (
            db.query(CloudAccount)
            .filter(
                CloudAccount.id == account_id,
                CloudAccount.user_id == str(user.id),
            )
            .first()
        )
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

    start = date.fromisoformat(period_start) if period_start else date.today().replace(day=1)

    budget = Budget(
        user_id=str(user.id),
        name=name,
        monthly_limit=monthly_limit,
        alert_threshold_percent=alert_threshold_percent,
        period_start=start,
        account_id=account_id if account_id else None,
    )
    db.add(budget)
    db.commit()
    return RedirectResponse(url="/budgets", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/budgets/{id}/delete")
async def delete_budget(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    budget = (
        db.query(Budget)
        .filter(
            Budget.id == id,
            Budget.user_id == str(user.id),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(budget)
    db.commit()
    return RedirectResponse(url="/budgets", status_code=status.HTTP_303_SEE_OTHER)
