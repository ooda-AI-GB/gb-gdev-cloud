from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from app.database import get_db
from app.models import CloudAccount, CloudResource, CostRecord, WasteAlert, Budget
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    # Get all accounts for this user
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .all()
    )

    if not accounts:
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "accounts": [],
                "total_spend": 0,
                "alert_count": 0,
                "resource_count": 0,
                "budget_limit": None,
                "waste_alerts": [],
                "cost_by_service": [],
            },
        )

    account_ids = [a.id for a in accounts]

    # Sum costs for current month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_spend = float(
        db.query(func.coalesce(func.sum(CostRecord.amount), 0))
        .filter(
            CostRecord.account_id.in_(account_ids),
            CostRecord.date >= month_start,
        )
        .scalar()
    )

    # Count active waste alerts
    waste_alerts = (
        db.query(WasteAlert)
        .filter(
            WasteAlert.account_id.in_(account_ids),
            WasteAlert.status == "open",
        )
        .order_by(WasteAlert.created_at.desc())
        .all()
    )

    # Count total resources
    resource_count = (
        db.query(CloudResource)
        .filter(CloudResource.account_id.in_(account_ids))
        .count()
    )

    # Get first budget limit for display
    budget = (
        db.query(Budget)
        .filter(Budget.user_id == str(user.id))
        .first()
    )
    budget_limit = budget.monthly_limit if budget else None

    # Cost by service for chart
    service_rows = (
        db.query(CostRecord.service, func.sum(CostRecord.amount))
        .filter(
            CostRecord.account_id.in_(account_ids),
            CostRecord.date >= month_start,
        )
        .group_by(CostRecord.service)
        .order_by(func.sum(CostRecord.amount).desc())
        .all()
    )
    cost_by_service = [
        {"service": row[0], "cost": float(row[1])} for row in service_rows
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "accounts": accounts,
            "total_spend": total_spend,
            "alert_count": len(waste_alerts),
            "resource_count": resource_count,
            "budget_limit": budget_limit,
            "waste_alerts": waste_alerts,
            "cost_by_service": cost_by_service,
        },
    )
