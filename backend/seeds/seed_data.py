"""
Seed script — run once against a fresh DB.
Usage: python -m seeds.seed_data
"""

import asyncio
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.common.models import (
    Bank, DocumentType, SystemParameter, InterestRateTable,
    TrackTypeEnum, LoanPurposeEnum,
)

SYSTEM_ADMIN_ID = "00000000-0000-0000-0000-000000000001"


async def seed_banks(session: AsyncSession) -> None:
    banks = [
        {"id": str(uuid.uuid4()), "name_he": "בנק הפועלים", "mortgage_hotline": "03-5670100", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "בנק לאומי", "mortgage_hotline": "076-8858888", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "בנק דיסקונט", "mortgage_hotline": "03-5145145", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "בנק מזרחי טפחות", "mortgage_hotline": "1-700-507-607", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "הבנק הבינלאומי", "mortgage_hotline": "03-5196060", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "בנק ירושלים", "mortgage_hotline": "02-6788888", "is_active": True},
        {"id": str(uuid.uuid4()), "name_he": "First International Bank", "mortgage_hotline": None, "is_active": True},
    ]
    for b in banks:
        session.add(Bank(**b))


async def seed_system_parameters(session: AsyncSession) -> None:
    params = [
        {"key": "cpi_annual_forecast", "value": "0.030000", "previous_value": None},
        {"key": "prime_rate", "value": "0.062500", "previous_value": None},
        # Regulatory constants — stored in DB but flagged as non-editable in the UI
        {"key": "max_financing_ratio_primary", "value": "0.750000", "previous_value": None},
        {"key": "max_financing_ratio_additional", "value": "0.500000", "previous_value": None},
        {"key": "max_financing_ratio_all_purpose", "value": "0.500000", "previous_value": None},
        {"key": "max_financing_ratio_improvement", "value": "0.700000", "previous_value": None},
        {"key": "max_financing_ratio_price_residents", "value": "0.900000", "previous_value": None},
        {"key": "min_equity_price_residents", "value": "100000.000000", "previous_value": None},
        {"key": "max_monthly_payment_ratio", "value": "0.400000", "previous_value": None},
        {"key": "max_borrower_age_at_end", "value": "85.000000", "previous_value": None},
    ]
    for p in params:
        session.add(SystemParameter(
            id=str(uuid.uuid4()),
            key=p["key"],
            value=p["value"],
            updated_by_admin_id=SYSTEM_ADMIN_ID,
            previous_value=p["previous_value"],
        ))


async def seed_interest_rates(session: AsyncSession) -> None:
    rates = [
        # Fixed, not CPI-linked, housing
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 4, "period_years_max": 10, "rate": "0.0450"},
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 11, "period_years_max": 20, "rate": "0.0480"},
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 21, "period_years_max": 30, "rate": "0.0510"},
        # Fixed, CPI-linked, housing
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 4, "period_years_max": 10, "rate": "0.0150"},
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 11, "period_years_max": 20, "rate": "0.0180"},
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 21, "period_years_max": 30, "rate": "0.0210"},
        # Variable, not CPI-linked, housing
        {"track_type": TrackTypeEnum.variable, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 6, "period_years_max": 15, "rate": "0.0420"},
        {"track_type": TrackTypeEnum.variable, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 16, "period_years_max": 30, "rate": "0.0450"},
        # Variable, CPI-linked, housing
        {"track_type": TrackTypeEnum.variable, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 6, "period_years_max": 15, "rate": "0.0120"},
        {"track_type": TrackTypeEnum.variable, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 16, "period_years_max": 30, "rate": "0.0150"},
        # Prime, housing (spread over prime rate)
        {"track_type": TrackTypeEnum.prime, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.housing, "period_years_min": 4, "period_years_max": 30, "rate": "0.0000"},
        # All-purpose variants
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": False, "loan_purpose": LoanPurposeEnum.all_purpose, "period_years_min": 4, "period_years_max": 30, "rate": "0.0600"},
        {"track_type": TrackTypeEnum.fixed, "cpi_linked": True, "loan_purpose": LoanPurposeEnum.all_purpose, "period_years_min": 4, "period_years_max": 30, "rate": "0.0350"},
    ]
    for r in rates:
        session.add(InterestRateTable(
            id=str(uuid.uuid4()),
            track_type=r["track_type"],
            cpi_linked=r["cpi_linked"],
            loan_purpose=r["loan_purpose"],
            period_years_min=r["period_years_min"],
            period_years_max=r["period_years_max"],
            rate=r["rate"],
            effective_from=date(2026, 1, 1),
            created_by_admin_id=SYSTEM_ADMIN_ID,
        ))


async def seed_document_types(session: AsyncSession) -> None:
    doc_types = [
        # Always required
        {
            "name_he": "תעודת זהות",
            "description_he": "תעודת זהות ישראלית בתוקף (שני צדדים)",
            "required_condition": {},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "ספח תעודת זהות",
            "description_he": "ספח תעודת הזהות כולל פרטי המשפחה",
            "required_condition": {},
            "required_for_principal_approval": True,
        },
        # Employment-based
        {
            "name_he": "תלושי שכר (3 חודשים אחרונים)",
            "description_he": "שלושה תלושי שכר עדכניים",
            "required_condition": {"employment_status": ["employee"]},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "אישור העסקה ממעסיק",
            "description_he": "מכתב מהמעסיק המאשר העסקה קבועה",
            "required_condition": {"employment_status": ["employee"]},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "דוח רווח והפסד (עצמאי)",
            "description_he": "דוח שנתי מרואה חשבון לשנה האחרונה",
            "required_condition": {"employment_status": ["self_employed", "controlling_shareholder"]},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "שומת מס",
            "description_he": "שומת מס לשנה האחרונה",
            "required_condition": {"employment_status": ["self_employed", "controlling_shareholder"]},
            "required_for_principal_approval": True,
        },
        # Property-related
        {
            "name_he": "חוזה רכישה",
            "description_he": "עותק חתום של חוזה הרכישה",
            "required_condition": {"purchase_status": ["signed_contract"]},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "נסח טאבו",
            "description_he": "נסח טאבו עדכני (לא יותר מ-30 יום)",
            "required_condition": {"property_registration_type": ["tabu"]},
            "required_for_principal_approval": True,
        },
        # Financial
        {
            "name_he": "דפי חשבון בנק (3 חודשים)",
            "description_he": "הדפסת פירוט עסקאות של חשבון הבנק העיקרי",
            "required_condition": {},
            "required_for_principal_approval": True,
        },
        {
            "name_he": "אישור יתרת קרן השתלמות",
            "description_he": "אישור יתרה ממבטח הקרן",
            "required_condition": {"has_savings_fund": True},
            "required_for_principal_approval": False,
        },
        # Citizenship / tax
        {
            "name_he": "אישור תושבות / מסמכי אזרחות נוספת",
            "description_he": "מסמכים לאימות אזרחות נוספת",
            "required_condition": {"has_additional_citizenship": True},
            "required_for_principal_approval": True,
        },
    ]
    for dt in doc_types:
        session.add(DocumentType(id=str(uuid.uuid4()), **dt))


async def main() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await seed_banks(session)
            await seed_system_parameters(session)
            await seed_interest_rates(session)
            await seed_document_types(session)
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
