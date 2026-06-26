"""
Integration test: Personal Area endpoints via the AUTH_BYPASS dev path.

Tests the real stack — dev-token auth ("Bearer dev-<role>"), the /me endpoint,
borrower auto-save, dynamic document generation, and document upload/review —
against the real Postgres DB. No Firebase, no dependency overrides.

Prereq: docker Postgres up + dev data seeded (seeds.seed_data.seed_dev_data).
Run alone (NOT with tests/unit which stub SQLAlchemy):
  python -m pytest tests/integration/test_personal_area_api.py -q -s
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

# Must be set BEFORE importing app.config.settings / app.main
os.environ["DATABASE_URL"] = "postgresql+asyncpg://simplesave:simplesave@localhost:5433/simplesave"
os.environ["AUTH_BYPASS"] = "true"
os.environ["ENVIRONMENT"] = "development"

import httpx

from app.main import app

CLIENT = {"Authorization": "Bearer dev-client"}
ADVISOR = {"Authorization": "Bearer dev-advisor"}


async def _run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. /me returns the seeded demo application with its borrower
        r = await c.get("/api/applications/me", headers=CLIENT)
        assert r.status_code == 200, (r.status_code, r.text)
        appdata = r.json()["application"]
        assert appdata is not None, "expected seeded demo application"
        assert appdata["tier"] == "online_guidance"
        assert appdata["advisor_name"], "advisor should be assigned"
        assert len(appdata["borrowers"]) >= 1
        b = appdata["borrowers"][0]
        assert b["first_name"] == "יוסי", b
        app_id = appdata["application_id"]
        borrower_id = b["id"]

        # 2. Borrower auto-save (PATCH) coerces types and persists
        r = await c.patch(
            f"/api/applications/{app_id}/borrowers/{borrower_id}",
            headers=CLIENT,
            json={"fields": {"net_income": "25500", "occupation": "בודק אוטומציה", "is_smoker": "true"}},
        )
        assert r.status_code == 200, (r.status_code, r.text)
        updated = r.json()
        assert updated["net_income"] == 25500.0, updated
        assert updated["occupation"] == "בודק אוטומציה"
        assert updated["is_smoker"] is True

        # 3. Dynamic document list generates from the borrower profile
        r = await c.get(f"/api/documents/application/{app_id}", headers=CLIENT)
        assert r.status_code == 200, (r.status_code, r.text)
        docs_payload = r.json()
        docs = docs_payload["documents"]
        assert len(docs) > 0, "expected generated documents"
        assert docs_payload["blocking_total"] > 0
        names = [d["name"] for d in docs]
        # employee profile -> pay stubs required; always -> ID
        assert any("תלושי שכר" in n for n in names), names
        assert any("תעודת זהות" in n for n in names), names

        target = next(d for d in docs if d["required_for_principal_approval"])

        # 4. Client uploads the document
        r = await c.patch(
            f"/api/documents/{target['id']}", headers=CLIENT,
            json={"action": "upload", "file_name": "tlush.pdf"},
        )
        assert r.status_code == 200, (r.status_code, r.text)
        assert r.json()["status"] == "uploaded"

        # 5. Client cannot approve (advisor-only) -> 403
        r = await c.patch(f"/api/documents/{target['id']}", headers=CLIENT, json={"action": "approve"})
        assert r.status_code == 403, (r.status_code, r.text)

        # 6. Advisor approves
        r = await c.patch(f"/api/documents/{target['id']}", headers=ADVISOR, json={"action": "approve"})
        assert r.status_code == 200, (r.status_code, r.text)
        assert r.json()["status"] == "approved"

        # 7. Advisor sees the client's application via the shared GET
        r = await c.get(f"/api/applications/{app_id}", headers=ADVISOR)
        assert r.status_code == 200, (r.status_code, r.text)

        print(
            f"PERSONAL AREA OK - app={app_id[:8]} borrower auto-save OK, "
            f"{len(docs)} docs generated ({docs_payload['blocking_total']} blocking), "
            "upload OK, client-approve blocked OK, advisor-approve OK"
        )


def test_personal_area_endpoints():
    asyncio.run(_run())


if __name__ == "__main__":
    asyncio.run(_run())
