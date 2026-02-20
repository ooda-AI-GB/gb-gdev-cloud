import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CloudAccount, CloudResource, CostRecord, WasteAlert
from app.routes import get_current_user, get_active_subscription
from typing import Any

try:
    from google import genai
except ImportError:
    genai = None

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/advisor", response_class=HTMLResponse)
async def advisor_studio(
    request: Request,
    user: Any = Depends(get_current_user),
    sub: Any = Depends(get_active_subscription),
):
    return templates.TemplateResponse(
        "advisor/studio.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.post("/api/advisor/query")
async def advisor_query(
    request: Request,
    user: Any = Depends(get_current_user),
    sub: Any = Depends(get_active_subscription),
    db: Session = Depends(get_db),
):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse({"error": "AI not configured"}, status_code=503)

    if not genai:
        return JSONResponse(
            {"error": "Google GenAI library not installed"}, status_code=500
        )

    body = await request.json()
    user_query = body.get("query", "").strip()
    if not user_query:
        return JSONResponse({"error": "Query is required"}, status_code=400)

    # Gather context about user's cloud infrastructure
    accounts = (
        db.query(CloudAccount)
        .filter(CloudAccount.user_id == str(user.id))
        .all()
    )
    account_ids = [a.id for a in accounts]

    resources = (
        db.query(CloudResource)
        .filter(CloudResource.account_id.in_(account_ids))
        .all()
    ) if account_ids else []

    active_alerts = (
        db.query(WasteAlert)
        .filter(
            WasteAlert.account_id.in_(account_ids),
            WasteAlert.status == "open",
        )
        .all()
    ) if account_ids else []

    # Build context string
    context_parts = []
    if accounts:
        context_parts.append(
            f"Cloud Accounts ({len(accounts)}):\n"
            + "\n".join(
                f"- {a.name} ({a.provider})" for a in accounts
            )
        )
    if resources:
        context_parts.append(
            f"Resources ({len(resources)}):\n"
            + "\n".join(
                f"- {r.name} ({r.resource_type}, {r.status})" for r in resources
            )
        )
    if active_alerts:
        context_parts.append(
            f"Active Waste Alerts ({len(active_alerts)}):\n"
            + "\n".join(
                f"- {a.title}: {a.description}" for a in active_alerts
            )
        )

    context = "\n\n".join(context_parts) if context_parts else "No cloud infrastructure data available yet."

    prompt = (
        "You are a cloud infrastructure advisor for Cloud Pro, a cloud cost management platform. "
        "Based on the user's cloud infrastructure data below, answer their question with specific, "
        "actionable recommendations.\n\n"
        f"Infrastructure Context:\n{context}\n\n"
        f"User Question: {user_query}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return JSONResponse({"response": response.text})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
