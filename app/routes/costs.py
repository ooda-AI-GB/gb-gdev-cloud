from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from app.database import get_db
from app.models import CloudAccount, CostRecord
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


@router.get("/costs", response_class=HTMLResponse)
async def cost_overview(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    account_ids = _get_account_ids(db, str(user.id))

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total cost this month
    total_cost = float(
        db.query(func.coalesce(func.sum(CostRecord.amount), 0))
        .filter(
            CostRecord.account_id.in_(account_ids),
            CostRecord.date >= month_start,
        )
        .scalar()
    ) if account_ids else 0

    # Daily average and projected
    days_elapsed = max((now - month_start).days, 1)
    daily_average = total_cost / days_elapsed
    days_in_month = 30
    projected_cost = daily_average * days_in_month

    return templates.TemplateResponse(
        "costs/overview.html",
        {
            "request": request,
            "user": user,
            "total_cost": total_cost,
            "daily_average": daily_average,
            "projected_cost": projected_cost,
        },
    )


@router.get("/api/costs/daily")
async def daily_costs(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    """Return daily cost aggregation for Chart.js."""
    account_ids = _get_account_ids(db, str(user.id))
    if not account_ids:
        return JSONResponse([])

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            func.date(CostRecord.date),
            func.sum(CostRecord.amount),
        )
        .filter(
            CostRecord.account_id.in_(account_ids),
            CostRecord.date >= month_start,
        )
        .group_by(func.date(CostRecord.date))
        .order_by(func.date(CostRecord.date))
        .all()
    )

    data = [{"date": str(row[0]), "cost": float(row[1])} for row in rows]
    return JSONResponse(data)


@router.get("/api/costs/by-service")
async def costs_by_service(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    """Return cost by service for Chart.js."""
    account_ids = _get_account_ids(db, str(user.id))
    if not account_ids:
        return JSONResponse([])

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(CostRecord.service, func.sum(CostRecord.amount))
        .filter(
            CostRecord.account_id.in_(account_ids),
            CostRecord.date >= month_start,
        )
        .group_by(CostRecord.service)
        .order_by(func.sum(CostRecord.amount).desc())
        .all()
    )

    data = [{"service": row[0], "cost": float(row[1])} for row in rows]
    return JSONResponse(data)
