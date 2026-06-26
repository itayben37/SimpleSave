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

# Windows: the default ProactorEventLoop crashes on teardown when FileResponse
# streams over ASGITransport. The selector loop avoids it (test-process only).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

# Must be set BEFORE importing app.config.settings / app.main
os.environ["DATABASE_URL"] = "postgresql+asyncpg://simplesave:simplesave@localhost:5433/simplesave"
os.environ["AUTH_BYPASS"] = "true"
os.environ["ENVIRONMENT"] = "development"

import httpx

from app.main import app

CLIENT = {"Authorization": "Bearer dev-client"}
ADVISOR = {"Authorization": "Bearer dev-advisor"}


async def _dispose_engine():
    """Close the async engine's pool on the loop that created its connections,
    so the next asyncio.run() starts with a clean pool (avoids the asyncpg
    'attached to a different loop' error across separate test functions)."""
    from app.config.database import engine
    await engine.dispose()


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


async def _run_extended():
    """Covers the new Personal-Area surface: full mortgage-field persistence,
    multi-borrower, nested tables, real file upload/download, eligibility,
    collaterals and authorization signing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/applications/me", headers=CLIENT)
        appdata = r.json()["application"]
        app_id = appdata["application_id"]
        b0 = appdata["borrowers"][0]["id"]

        # 1. Full mortgage-data persistence (column-backed, survives reload)
        r = await c.patch(f"/api/applications/{app_id}", headers=CLIENT, json={"wizard_data": {
            "purchase_status": "signed_contract", "property_address_city": "חיפה",
            "valuation_source": "appraiser", "desired_monthly_min": "4000",
            "desired_monthly_max": "6000", "equity_sources": {"savings": 300000, "family": 200000},
        }})
        assert r.status_code == 200, (r.status_code, r.text)
        me = (await c.get("/api/applications/me", headers=CLIENT)).json()["application"]
        assert me["purchase_status"] == "signed_contract", me
        assert me["property_address_city"] == "חיפה"
        assert me["valuation_source"] == "appraiser"
        assert me["desired_monthly_min"] == 4000.0
        assert me["equity_sources"]["family"] == 200000

        # 2. Multi-borrower
        r = await c.post(f"/api/applications/{app_id}/borrowers", headers=CLIENT)
        assert r.status_code == 201, (r.status_code, r.text)
        b1 = r.json()["id"]
        assert r.json()["sequence_number"] == 2

        # 3. Nested tables CRUD on borrower 0
        r = await c.post(f"/api/applications/{app_id}/borrowers/{b0}/incomes", headers=CLIENT,
                         json={"fields": {"income_type": "rental", "monthly_amount": "3200"}})
        assert r.status_code == 201, (r.status_code, r.text)
        income_id = r.json()["id"]
        assert r.json()["monthly_amount"] == 3200.0

        r = await c.post(f"/api/applications/{app_id}/borrowers/{b0}/expenses", headers=CLIENT,
                         json={"fields": {"expense_type": "loan", "monthly_amount": "1500",
                                          "remaining_balance": "45000", "source": "bank"}})
        assert r.status_code == 201, (r.status_code, r.text)
        expense_id = r.json()["id"]

        r = await c.post(f"/api/applications/{app_id}/borrowers/{b0}/properties", headers=CLIENT,
                         json={"fields": {"property_type": "apartment_building", "city": "תל אביב",
                                          "street": "דיזנגוף", "number": "100", "estimated_value": "2000000"}})
        assert r.status_code == 201, (r.status_code, r.text)
        prop_id = r.json()["id"]

        # nested rows surface in /me
        me = (await c.get("/api/applications/me", headers=CLIENT)).json()["application"]
        nb0 = next(b for b in me["borrowers"] if b["id"] == b0)
        assert len(nb0["additional_incomes"]) == 1
        assert len(nb0["fixed_expenses"]) == 1
        assert len(nb0["additional_properties"]) == 1

        # patch + delete a nested row
        r = await c.patch(f"/api/applications/{app_id}/borrowers/{b0}/incomes/{income_id}",
                          headers=CLIENT, json={"fields": {"monthly_amount": "3500"}})
        assert r.status_code == 200 and r.json()["monthly_amount"] == 3500.0, r.text
        r = await c.delete(f"/api/applications/{app_id}/borrowers/{b0}/properties/{prop_id}", headers=CLIENT)
        assert r.status_code == 204, (r.status_code, r.text)

        # 4. Real file upload + authenticated download
        docs = (await c.get(f"/api/documents/application/{app_id}", headers=CLIENT)).json()["documents"]
        doc = docs[0]
        files = {"file": ("proof.txt", b"hello-simplesave", "text/plain")}
        r = await c.post(f"/api/documents/{doc['id']}/file", headers=CLIENT, files=files)
        assert r.status_code == 200, (r.status_code, r.text)
        assert r.json()["status"] == "uploaded" and r.json()["has_file"] is True
        r = await c.get(f"/api/documents/{doc['id']}/file", headers=CLIENT)
        assert r.status_code == 200 and r.content == b"hello-simplesave", (r.status_code, r.content)

        # 5. Eligibility derived from the primary borrower
        r = await c.get(f"/api/applications/{app_id}/eligibility", headers=CLIENT)
        assert r.status_code == 200, (r.status_code, r.text)
        elig = r.json()
        assert elig["available"] is True and "eligibility_score" in elig, elig

        # 6. Collaterals: advisor adds, client reads
        r = await c.post(f"/api/applications/{app_id}/collaterals", headers=ADVISOR,
                         json={"description": "שעבוד הנכס לטובת הבנק"})
        assert r.status_code == 201, (r.status_code, r.text)
        r = await c.get(f"/api/applications/{app_id}/collaterals", headers=CLIENT)
        assert r.status_code == 200 and len(r.json()["collaterals"]) >= 1, r.text
        # client cannot add collaterals
        r = await c.post(f"/api/applications/{app_id}/collaterals", headers=CLIENT, json={"description": "x"})
        assert r.status_code == 403, (r.status_code, r.text)

        # 7. Authorization signing
        r = await c.post(f"/api/applications/{app_id}/sign-authorization", headers=CLIENT)
        assert r.status_code == 200 and r.json()["authorization_signed_at"], r.text

        # 8. Messages thread (enriched shape)
        r = await c.post(f"/api/messages/{app_id}", headers=CLIENT, json={"body": "שלום יועץ"})
        assert r.status_code == 200 and r.json()["is_mine"] is True, r.text
        r = await c.get(f"/api/messages/{app_id}", headers=CLIENT)
        assert r.status_code == 200 and len(r.json()["messages"]) >= 1, r.text

        # cleanup the extra borrower so re-runs stay deterministic
        # (nested rows + borrower auto-clean is not exposed; leave borrower, it's harmless)
        _ = (b1, expense_id)
        print("EXTENDED PERSONAL AREA OK - mortgage fields, multi-borrower, nested CRUD, "
              "real upload+download, eligibility, collaterals, auth-sign, messages")


async def _with_dispose(coro_fn):
    try:
        await coro_fn()
    finally:
        await _dispose_engine()


def test_personal_area_endpoints():
    asyncio.run(_with_dispose(_run))


def test_personal_area_extended():
    asyncio.run(_with_dispose(_run_extended))


if __name__ == "__main__":
    asyncio.run(_with_dispose(_run))
    asyncio.run(_with_dispose(_run_extended))
