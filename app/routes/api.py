from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, Optional
from datetime import datetime, date
from pydantic import BaseModel

from app.models import (
    CloudAccount, CloudResource, CostRecord, UtilizationSnapshot,
    WasteAlert, Budget, OptimizationRecommendation, AIInsight,
)
from app.database import get_db
from app.routes import get_current_user

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def to_dict(obj) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict."""
    result = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, date):
            val = val.isoformat()
        result[col.name] = val
    return result


def get_or_404(db: Session, model, id_val: int, label: str):
    obj = db.get(model, id_val)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} {id_val} not found")
    return obj


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CloudAccountCreate(BaseModel):
    user_id: str
    provider: str
    name: str
    account_id: str
    credentials_ref: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = "connected"


class CloudAccountUpdate(BaseModel):
    user_id: Optional[str] = None
    provider: Optional[str] = None
    name: Optional[str] = None
    account_id: Optional[str] = None
    credentials_ref: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None


class CloudResourceCreate(BaseModel):
    account_id: int
    resource_id: str
    resource_type: str
    name: str
    region: Optional[str] = None
    status: Optional[str] = "unknown"
    provider_status: Optional[str] = None
    config: Optional[str] = None
    tags: Optional[str] = None


class CloudResourceUpdate(BaseModel):
    account_id: Optional[int] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    name: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    provider_status: Optional[str] = None
    config: Optional[str] = None
    tags: Optional[str] = None


class CostRecordCreate(BaseModel):
    account_id: int
    resource_id: Optional[int] = None
    date: date
    service: str
    sku: Optional[str] = None
    amount: Optional[float] = 0
    currency: Optional[str] = "USD"
    usage_quantity: Optional[float] = None
    usage_unit: Optional[str] = None


class CostRecordUpdate(BaseModel):
    account_id: Optional[int] = None
    resource_id: Optional[int] = None
    date: Optional[date] = None
    service: Optional[str] = None
    sku: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    usage_quantity: Optional[float] = None
    usage_unit: Optional[str] = None


class UtilizationSnapshotCreate(BaseModel):
    resource_id: int
    snapshot_time: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    network_in_bytes: Optional[int] = None
    network_out_bytes: Optional[int] = None
    request_count: Optional[int] = None
    error_count: Optional[int] = None


class UtilizationSnapshotUpdate(BaseModel):
    resource_id: Optional[int] = None
    snapshot_time: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    network_in_bytes: Optional[int] = None
    network_out_bytes: Optional[int] = None
    request_count: Optional[int] = None
    error_count: Optional[int] = None


class WasteAlertCreate(BaseModel):
    account_id: int
    resource_id: Optional[int] = None
    alert_type: str
    title: str
    description: str
    severity: str
    estimated_monthly_waste: Optional[float] = 0
    status: Optional[str] = "open"
    recommendation: Optional[str] = None


class WasteAlertUpdate(BaseModel):
    account_id: Optional[int] = None
    resource_id: Optional[int] = None
    alert_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    estimated_monthly_waste: Optional[float] = None
    status: Optional[str] = None
    recommendation: Optional[str] = None
    resolved_at: Optional[datetime] = None


class BudgetCreate(BaseModel):
    user_id: str
    account_id: Optional[int] = None
    name: str
    monthly_limit: float
    alert_threshold_percent: Optional[float] = 80.0
    current_spend: Optional[float] = 0
    period_start: date
    enabled: Optional[bool] = True


class BudgetUpdate(BaseModel):
    user_id: Optional[str] = None
    account_id: Optional[int] = None
    name: Optional[str] = None
    monthly_limit: Optional[float] = None
    alert_threshold_percent: Optional[float] = None
    current_spend: Optional[float] = None
    period_start: Optional[date] = None
    enabled: Optional[bool] = None


class OptimizationRecommendationCreate(BaseModel):
    account_id: int
    resource_id: Optional[int] = None
    category: str
    title: str
    description: str
    estimated_monthly_savings: Optional[float] = 0
    effort: str
    status: Optional[str] = "pending"
    model_used: Optional[str] = None


class OptimizationRecommendationUpdate(BaseModel):
    account_id: Optional[int] = None
    resource_id: Optional[int] = None
    category: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_monthly_savings: Optional[float] = None
    effort: Optional[str] = None
    status: Optional[str] = None
    model_used: Optional[str] = None


class AIInsightCreate(BaseModel):
    account_id: Optional[int] = None
    insight_type: str
    title: str
    description: str
    severity: Optional[str] = "info"
    data_context: Optional[str] = None
    model_used: Optional[str] = None
    acknowledged: Optional[bool] = False


class AIInsightUpdate(BaseModel):
    account_id: Optional[int] = None
    insight_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    data_context: Optional[str] = None
    model_used: Optional[str] = None
    acknowledged: Optional[bool] = None


# ── CloudAccount CRUD ─────────────────────────────────────────────────────────

@router.get("/accounts")
def list_accounts(
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(CloudAccount)
    if status:
        q = q.filter(CloudAccount.status == status)
    if provider:
        q = q.filter(CloudAccount.provider == provider)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/accounts/{account_id}")
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, CloudAccount, account_id, "CloudAccount"))


@router.post("/accounts", status_code=201)
def create_account(
    body: CloudAccountCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = CloudAccount(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    body: CloudAccountUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CloudAccount, account_id, "CloudAccount")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CloudAccount, account_id, "CloudAccount")
    db.delete(obj)
    db.commit()


# ── CloudResource CRUD ────────────────────────────────────────────────────────

@router.get("/resources")
def list_resources(
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    account_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(CloudResource)
    if status:
        q = q.filter(CloudResource.status == status)
    if resource_type:
        q = q.filter(CloudResource.resource_type == resource_type)
    if account_id is not None:
        q = q.filter(CloudResource.account_id == account_id)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/resources/{resource_id}")
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, CloudResource, resource_id, "CloudResource"))


@router.post("/resources", status_code=201)
def create_resource(
    body: CloudResourceCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = CloudResource(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/resources/{resource_id}")
def update_resource(
    resource_id: int,
    body: CloudResourceUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CloudResource, resource_id, "CloudResource")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CloudResource, resource_id, "CloudResource")
    db.delete(obj)
    db.commit()


# ── CostRecord CRUD ───────────────────────────────────────────────────────────

@router.get("/cost-records")
def list_cost_records(
    account_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    service: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(CostRecord)
    if account_id is not None:
        q = q.filter(CostRecord.account_id == account_id)
    if resource_id is not None:
        q = q.filter(CostRecord.resource_id == resource_id)
    if service:
        q = q.filter(CostRecord.service == service)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/cost-records/{record_id}")
def get_cost_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, CostRecord, record_id, "CostRecord"))


@router.post("/cost-records", status_code=201)
def create_cost_record(
    body: CostRecordCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = CostRecord(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/cost-records/{record_id}")
def update_cost_record(
    record_id: int,
    body: CostRecordUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CostRecord, record_id, "CostRecord")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/cost-records/{record_id}", status_code=204)
def delete_cost_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, CostRecord, record_id, "CostRecord")
    db.delete(obj)
    db.commit()


# ── UtilizationSnapshot CRUD ──────────────────────────────────────────────────

@router.get("/utilization-snapshots")
def list_utilization_snapshots(
    resource_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(UtilizationSnapshot)
    if resource_id is not None:
        q = q.filter(UtilizationSnapshot.resource_id == resource_id)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/utilization-snapshots/{snapshot_id}")
def get_utilization_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, UtilizationSnapshot, snapshot_id, "UtilizationSnapshot"))


@router.post("/utilization-snapshots", status_code=201)
def create_utilization_snapshot(
    body: UtilizationSnapshotCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = UtilizationSnapshot(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/utilization-snapshots/{snapshot_id}")
def update_utilization_snapshot(
    snapshot_id: int,
    body: UtilizationSnapshotUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, UtilizationSnapshot, snapshot_id, "UtilizationSnapshot")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/utilization-snapshots/{snapshot_id}", status_code=204)
def delete_utilization_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, UtilizationSnapshot, snapshot_id, "UtilizationSnapshot")
    db.delete(obj)
    db.commit()


# ── WasteAlert CRUD ───────────────────────────────────────────────────────────

@router.get("/waste-alerts")
def list_waste_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    account_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(WasteAlert)
    if status:
        q = q.filter(WasteAlert.status == status)
    if severity:
        q = q.filter(WasteAlert.severity == severity)
    if account_id is not None:
        q = q.filter(WasteAlert.account_id == account_id)
    if resource_id is not None:
        q = q.filter(WasteAlert.resource_id == resource_id)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/waste-alerts/{alert_id}")
def get_waste_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, WasteAlert, alert_id, "WasteAlert"))


@router.post("/waste-alerts", status_code=201)
def create_waste_alert(
    body: WasteAlertCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = WasteAlert(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/waste-alerts/{alert_id}")
def update_waste_alert(
    alert_id: int,
    body: WasteAlertUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, WasteAlert, alert_id, "WasteAlert")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/waste-alerts/{alert_id}", status_code=204)
def delete_waste_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, WasteAlert, alert_id, "WasteAlert")
    db.delete(obj)
    db.commit()


# ── Budget CRUD ───────────────────────────────────────────────────────────────

@router.get("/budgets")
def list_budgets(
    account_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(Budget)
    if account_id is not None:
        q = q.filter(Budget.account_id == account_id)
    if enabled is not None:
        q = q.filter(Budget.enabled == enabled)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/budgets/{budget_id}")
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Budget, budget_id, "Budget"))


@router.post("/budgets", status_code=201)
def create_budget(
    body: BudgetCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = Budget(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/budgets/{budget_id}")
def update_budget(
    budget_id: int,
    body: BudgetUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, Budget, budget_id, "Budget")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, Budget, budget_id, "Budget")
    db.delete(obj)
    db.commit()


# ── OptimizationRecommendation CRUD ──────────────────────────────────────────

@router.get("/recommendations")
def list_recommendations(
    status: Optional[str] = None,
    category: Optional[str] = None,
    account_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(OptimizationRecommendation)
    if status:
        q = q.filter(OptimizationRecommendation.status == status)
    if category:
        q = q.filter(OptimizationRecommendation.category == category)
    if account_id is not None:
        q = q.filter(OptimizationRecommendation.account_id == account_id)
    if resource_id is not None:
        q = q.filter(OptimizationRecommendation.resource_id == resource_id)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/recommendations/{rec_id}")
def get_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, OptimizationRecommendation, rec_id, "OptimizationRecommendation"))


@router.post("/recommendations", status_code=201)
def create_recommendation(
    body: OptimizationRecommendationCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = OptimizationRecommendation(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/recommendations/{rec_id}")
def update_recommendation(
    rec_id: int,
    body: OptimizationRecommendationUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, OptimizationRecommendation, rec_id, "OptimizationRecommendation")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/recommendations/{rec_id}", status_code=204)
def delete_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, OptimizationRecommendation, rec_id, "OptimizationRecommendation")
    db.delete(obj)
    db.commit()


# ── AIInsight CRUD ────────────────────────────────────────────────────────────

@router.get("/insights")
def list_insights(
    acknowledged: Optional[bool] = None,
    severity: Optional[str] = None,
    account_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(AIInsight)
    if acknowledged is not None:
        q = q.filter(AIInsight.acknowledged == acknowledged)
    if severity:
        q = q.filter(AIInsight.severity == severity)
    if account_id is not None:
        q = q.filter(AIInsight.account_id == account_id)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/insights/{insight_id}")
def get_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, AIInsight, insight_id, "AIInsight"))


@router.post("/insights", status_code=201)
def create_insight(
    body: AIInsightCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = AIInsight(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.put("/insights/{insight_id}")
def update_insight(
    insight_id: int,
    body: AIInsightUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, AIInsight, insight_id, "AIInsight")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return to_dict(obj)


@router.delete("/insights/{insight_id}", status_code=204)
def delete_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    obj = get_or_404(db, AIInsight, insight_id, "AIInsight")
    db.delete(obj)
    db.commit()


# ── Dashboard aggregate stats ─────────────────────────────────────────────────

@router.get("/dashboard")
def api_dashboard(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    total_accounts = db.query(func.count(CloudAccount.id)).scalar()
    total_resources = db.query(func.count(CloudResource.id)).scalar()
    total_cost_records = db.query(func.count(CostRecord.id)).scalar()
    total_snapshots = db.query(func.count(UtilizationSnapshot.id)).scalar()
    total_waste_alerts = db.query(func.count(WasteAlert.id)).scalar()
    open_waste_alerts = db.query(func.count(WasteAlert.id)).filter(WasteAlert.status == "open").scalar()
    total_budgets = db.query(func.count(Budget.id)).scalar()
    total_recommendations = db.query(func.count(OptimizationRecommendation.id)).scalar()
    pending_recommendations = (
        db.query(func.count(OptimizationRecommendation.id))
        .filter(OptimizationRecommendation.status == "pending")
        .scalar()
    )
    total_insights = db.query(func.count(AIInsight.id)).scalar()
    unacknowledged_insights = (
        db.query(func.count(AIInsight.id))
        .filter(AIInsight.acknowledged == False)  # noqa: E712
        .scalar()
    )
    total_cost = db.query(func.sum(CostRecord.amount)).scalar() or 0.0
    total_waste = (
        db.query(func.sum(WasteAlert.estimated_monthly_waste))
        .filter(WasteAlert.status == "open")
        .scalar()
    ) or 0.0
    total_savings = (
        db.query(func.sum(OptimizationRecommendation.estimated_monthly_savings))
        .filter(OptimizationRecommendation.status == "pending")
        .scalar()
    ) or 0.0

    return {
        "accounts": {"total": total_accounts},
        "resources": {"total": total_resources},
        "cost_records": {"total": total_cost_records, "total_spend": round(total_cost, 2)},
        "utilization_snapshots": {"total": total_snapshots},
        "waste_alerts": {
            "total": total_waste_alerts,
            "open": open_waste_alerts,
            "estimated_monthly_waste": round(total_waste, 2),
        },
        "budgets": {"total": total_budgets},
        "recommendations": {
            "total": total_recommendations,
            "pending": pending_recommendations,
            "estimated_monthly_savings": round(total_savings, 2),
        },
        "insights": {"total": total_insights, "unacknowledged": unacknowledged_insights},
    }
