import random
import json
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    CloudAccount,
    CloudResource,
    CostRecord,
    WasteAlert,
    Budget,
    OptimizationRecommendation,
    AIInsight,
)


def seed_data(db: Session):
    """Seed the database with Cloud Pro demo data if empty."""
    existing = db.query(CloudAccount).first()
    if existing:
        return

    random.seed(42)

    # ── 1. Cloud Accounts ──────────────────────────────────────────────
    prod_account = CloudAccount(
        user_id="__seed__",
        name="Gigabox Production",
        provider="gcp",
        account_id="gigabox-prod-2025",
        region="us-central1",
        status="connected",
    )
    dev_account = CloudAccount(
        user_id="__seed__",
        name="Gigabox Dev",
        provider="gcp",
        account_id="gigabox-dev-2025",
        region="us-central1",
        status="connected",
    )
    db.add_all([prod_account, dev_account])
    db.flush()

    # ── 2. Cloud Resources ─────────────────────────────────────────────
    viv_api_vm = CloudResource(
        account_id=prod_account.id,
        resource_id="i-viv-api-001",
        resource_type="vm",
        name="viv-api-vm",
        status="running",
        config=json.dumps({"vcpu": 2, "memory_gb": 8, "disk_gb": 50}),
    )
    axiom_db = CloudResource(
        account_id=prod_account.id,
        resource_id="db-axiom-001",
        resource_type="database",
        name="axiom-db",
        status="running",
        config=json.dumps({"engine": "postgresql", "vcpu": 1, "memory_gb": 3.75, "storage_gb": 20}),
    )
    redis_cache = CloudResource(
        account_id=prod_account.id,
        resource_id="cache-redis-001",
        resource_type="cache",
        name="redis-cache",
        status="running",
        config=json.dumps({"engine": "redis", "memory_gb": 1}),
    )
    cc_worker = CloudResource(
        account_id=dev_account.id,
        resource_id="i-ccworker-001",
        resource_type="vm",
        name="cc-worker-01",
        status="running",
        config=json.dumps({"vcpu": 2, "memory_gb": 4, "disk_gb": 30}),
    )
    slackbot_rogue = CloudResource(
        account_id=dev_account.id,
        resource_id="run-slackbot-001",
        resource_type="container",
        name="slackbot-v01-ROGUE",
        status="error",
        config=json.dumps({"cpu": 1, "memory_mb": 256, "min_instances": 0, "max_instances": 10}),
    )
    db.add_all([viv_api_vm, axiom_db, redis_cache, cc_worker, slackbot_rogue])
    db.flush()

    # ── 3. Cost Records (30 days) ──────────────────────────────────────
    today = date.today()
    cost_records = []

    for i in range(30):
        record_date = today - timedelta(days=i)

        # Cloud SQL (~$3.20/day)
        cost_records.append(CostRecord(
            account_id=prod_account.id,
            resource_id=axiom_db.id,
            service="Cloud SQL",
            date=record_date,
            amount=round(random.uniform(3.0, 3.4), 2),
        ))

        # Compute Engine (~$2.30/day)
        cost_records.append(CostRecord(
            account_id=prod_account.id,
            resource_id=viv_api_vm.id,
            service="Compute Engine",
            date=record_date,
            amount=round(random.uniform(2.1, 2.5), 2),
        ))

        # Memorystore (~$2.00/day)
        cost_records.append(CostRecord(
            account_id=prod_account.id,
            service="Memorystore",
            date=record_date,
            amount=round(random.uniform(1.8, 2.2), 2),
        ))

        # Cloud Run: $0.40/day normally, $20/day for the last 2 days (spike!)
        cloud_run_cost = 20.0 if i < 2 else 0.40
        cost_records.append(CostRecord(
            account_id=prod_account.id,
            resource_id=slackbot_rogue.id,
            service="Cloud Run",
            date=record_date,
            amount=cloud_run_cost,
        ))

    db.add_all(cost_records)

    # ── 4. Waste Alerts ────────────────────────────────────────────────
    waste_crash_loop = WasteAlert(
        account_id=dev_account.id,
        resource_id=slackbot_rogue.id,
        alert_type="crash_loop",
        severity="critical",
        title="Cloud Run crash-loop: slackbot-v01",
        description="Container restarted 847 times in 48h. CPU at 100%.",
        estimated_monthly_waste=600.0,
        status="open",
        recommendation="Delete this Cloud Run service.",
    )
    waste_oversized = WasteAlert(
        account_id=prod_account.id,
        resource_id=axiom_db.id,
        alert_type="oversized",
        severity="low",
        title="Cloud SQL potentially oversized",
        description="axiom-db averages 10% CPU/25% memory. Consider downsizing.",
        estimated_monthly_waste=20.0,
        status="open",
        recommendation="Evaluate db-f1-micro vs current instance.",
    )
    db.add_all([waste_crash_loop, waste_oversized])

    # ── 5. Budget ──────────────────────────────────────────────────────
    first_of_month = today.replace(day=1)
    budget = Budget(
        user_id="__seed__",
        name="Monthly Infrastructure",
        monthly_limit=300.0,
        alert_threshold_percent=80.0,
        current_spend=268.0,
        period_start=first_of_month,
    )
    db.add(budget)

    # ── 6. AI Insight ──────────────────────────────────────────────────
    insight = AIInsight(
        account_id=prod_account.id,
        insight_type="anomaly",
        severity="critical",
        title="Cost Anomaly: Cloud Run",
        description="Cloud Run spend increased 1200% over 48 hours due to slackbot-v01 crash-loop.",
        model_used="gemini-2.5-flash",
    )
    db.add(insight)

    # ── 7. Optimization Recommendation ─────────────────────────────────
    recommendation = OptimizationRecommendation(
        account_id=dev_account.id,
        resource_id=slackbot_rogue.id,
        category="deletion",
        title="Delete rogue slackbot-v01",
        description="Crash-looping container wasting $600/month.",
        estimated_monthly_savings=600.0,
        effort="low",
        status="pending",
        model_used="gemini-2.5-flash",
    )
    db.add(recommendation)

    db.commit()
