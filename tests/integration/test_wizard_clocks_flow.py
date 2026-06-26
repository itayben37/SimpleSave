"""
Integration test: full guest wizard -> clocks flow against the real Postgres DB.

Exercises the endpoints that were previously broken (model/router desync):
  POST /api/applications
  PATCH /api/applications/{id}
  GET  /api/applications/{id}/wizard-state
  GET  /api/calculations/clocks/{id}   (lazy-generates 5 clocks)

Run from the repo root with the Postgres container up (docker compose):
  python -m pytest tests/integration/test_wizard_clocks_flow.py -q

NOTE: this file deliberately does NOT stub SQLAlchemy/Firebase like the
tests/unit suite, so run it on its own (not together with tests/unit).
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

DB_URL = "postgresql+asyncpg://simplesave:simplesave@localhost:5433/simplesave"
os.environ.setdefault("DATABASE_URL", DB_URL)

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.common.auth import get_current_user
from app.config.database import get_db
from app.common.models import (
    User, Application, ClockResult, AuditLog, RoleEnum,
)

_engine = create_async_engine(DB_URL)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


async def _override_get_db():
    async with _Session() as s:
        yield s


async def _run_flow():
    # 1. Create a throwaway client user that the application will belong to.
    test_user = User(
        id=str(uuid.uuid4()),
        firebase_uid=f"test-{uuid.uuid4()}",
        email=f"test-{uuid.uuid4()}@example.com",
        role=RoleEnum.client,
        full_name="בודק אוטומטי",
        is_active=True,
    )
    async with _Session() as s:
        s.add(test_user)
        await s.commit()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    app_id = None
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 2. Create application
            r = await client.post("/api/applications", json={})
            assert r.status_code == 201, (r.status_code, r.text)
            app_id = r.json()["application_id"]

            # 3. Auto-save wizard answers
            wizard = {
                "loan_purpose": "primary_residence",
                "property_value": "1500000",
                "loan_amount": "1000000",
                "num_borrowers": 2,
                "first_home": True,
                "marital_status": "married",
                "total_monthly_income": "20000",
                "primary_borrower_birth_date": "1985-03-15",
            }
            r = await client.patch(f"/api/applications/{app_id}", json={"wizard_data": wizard})
            assert r.status_code == 200, (r.status_code, r.text)

            # 4. Submit (advance status)
            r = await client.patch(
                f"/api/applications/{app_id}",
                json={"wizard_data": wizard, "advance_status": True},
            )
            assert r.status_code == 200, (r.status_code, r.text)
            assert r.json()["status"] == "QUESTIONNAIRE_COMPLETE", r.json()

            # 5. wizard-state round-trips the data (raw answers + promoted columns)
            r = await client.get(f"/api/applications/{app_id}/wizard-state")
            assert r.status_code == 200, (r.status_code, r.text)
            wd = r.json()["wizard_data"]
            assert wd["loan_purpose"] == "primary_residence", wd
            assert wd["num_borrowers"] == 2, wd
            assert float(wd["loan_amount"]) == 1000000.0, wd

            # 6. Clocks lazily generate — expect 5 with positive payments
            r = await client.get(f"/api/calculations/clocks/{app_id}")
            assert r.status_code == 200, (r.status_code, r.text)
            clocks = r.json()["clocks"]
            assert len(clocks) == 5, f"expected 5 clocks, got {len(clocks)}: {clocks}"

            numbers = [c["clock_number"] for c in clocks]
            assert numbers == [1, 2, 3, 4, 5], numbers

            for c in clocks:
                assert c["monthly_payment_initial"] > 0, c
                assert c["total_payment"] > c["total_interest"] > 0, c
                assert c["risk_level"] in ("low", "medium", "high"), c
                assert len(c["stacked_bar_data"]) > 0, c
                assert len(c["cumulative_totals_data"]) > 0, c

            # Risk should rise from clock 1 (all fixed) to clock 5 (prime+variable)
            risk1 = next(c for c in clocks if c["clock_number"] == 1)["risk_score_percentage"]
            risk5 = next(c for c in clocks if c["clock_number"] == 5)["risk_score_percentage"]
            assert risk1 < risk5, (risk1, risk5)

            print(
                "FLOW OK — 5 clocks generated. "
                f"clock1 monthly=₪{clocks[0]['monthly_payment_initial']:.0f} risk={risk1}%, "
                f"clock5 monthly=₪{clocks[4]['monthly_payment_initial']:.0f} risk={risk5}%"
            )
    finally:
        # Cleanup: remove everything we created
        app.dependency_overrides.clear()
        async with _Session() as s:
            if app_id:
                await s.execute(delete(ClockResult).where(ClockResult.application_id == app_id))
                await s.execute(delete(Application).where(Application.id == app_id))
            await s.execute(delete(AuditLog).where(AuditLog.actor_id == test_user.id))
            await s.execute(delete(User).where(User.id == test_user.id))
            await s.commit()
        await _engine.dispose()


def test_wizard_to_clocks_flow():
    asyncio.run(_run_flow())


if __name__ == "__main__":
    asyncio.run(_run_flow())
