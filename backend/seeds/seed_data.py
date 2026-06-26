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
    User, TrackTypeEnum, LoanPurposeEnum, RoleEnum,
    Mix, MixTrack, RiskLevelEnum, AmortizationTypeEnum,
)

SYSTEM_ADMIN_ID = "00000000-0000-0000-0000-000000000001"


async def seed_system_admin(session: AsyncSession) -> None:
    """Insert the system admin user that seeds reference via FK."""
    session.add(User(
        id=SYSTEM_ADMIN_ID,
        firebase_uid="system-admin",
        email="admin@simplesave.co.il",
        full_name="System Admin",
        role=RoleEnum.admin,
        is_active=True,
    ))


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


async def seed_mixes(session: AsyncSession) -> None:
    """
    Seed the 5 "clocks" (mixes), each a portfolio of tracks summing to 100%.
    Risk rises from clock 1 (all fixed) to clock 5 (prime + variable).
    Track periods are chosen to fall inside the seeded interest-rate ranges.
    spec: docs/specs/calculations/10-clocks-mix-generation.md, QA §6
    """
    F, V, P = TrackTypeEnum.fixed, TrackTypeEnum.variable, TrackTypeEnum.prime
    SP = AmortizationTypeEnum.spitzer

    # (clock_number, name, risk_level, [ (track_type, cpi_linked, period_years, pct, interval) ])
    mixes = [
        (1, "שמרני", RiskLevelEnum.low, [
            (F, False, 20, "100.00", None),
        ]),
        (2, "סולידי", RiskLevelEnum.low, [
            (F, False, 20, "70.00", None),
            (F, True, 20, "30.00", None),
        ]),
        (3, "מאוזן", RiskLevelEnum.medium, [
            (F, False, 25, "40.00", None),
            (V, False, 10, "30.00", 60),
            (P, False, 15, "30.00", None),
        ]),
        (4, "דינמי", RiskLevelEnum.high, [
            (F, False, 25, "30.00", None),
            (V, True, 10, "30.00", 60),
            (P, False, 10, "40.00", None),
        ]),
        (5, "אגרסיבי", RiskLevelEnum.high, [
            (V, False, 10, "50.00", 60),
            (P, False, 15, "50.00", None),
        ]),
    ]

    for clock_number, name, risk, tracks in mixes:
        mix_id = str(uuid.uuid4())
        session.add(Mix(
            id=mix_id, clock_number=clock_number, name=name,
            risk_level=risk, is_active=True,
        ))
        for seq, (tt, cpi, years, pct, interval) in enumerate(tracks, start=1):
            session.add(MixTrack(
                id=str(uuid.uuid4()),
                mix_id=mix_id,
                sequence=seq,
                track_type=tt,
                cpi_linked=cpi,
                period_years=years,
                rate_change_interval_months=interval,
                amortization_type=SP,
                percentage_of_mix=pct,
                spread="0.0000",
            ))


async def seed_dev_data(session: AsyncSession) -> None:
    """
    Idempotent dev/sanity-check fixtures used by AUTH_BYPASS:
    one user per role (dev-client / dev-advisor / dev-admin) plus a demo
    application (owned by dev-client, assigned to dev-advisor) with a filled
    borrower so the Personal Area shows real data immediately.
    """
    from datetime import date as _date
    from app.common.models import (
        Application, Borrower, ApplicationStatusEnum, LoanTypeEnum, TierEnum,
        GenderEnum, MaritalStatusEnum, EducationEnum, EmploymentStatusEnum,
    )
    from sqlalchemy import select

    roles = {
        "dev-client": RoleEnum.client,
        "dev-advisor": RoleEnum.advisor,
        "dev-admin": RoleEnum.admin,
    }
    users: dict[str, User] = {}
    for uid, role in roles.items():
        existing = (await session.execute(select(User).where(User.firebase_uid == uid))).scalar_one_or_none()
        if existing is None:
            existing = User(
                id=str(uuid.uuid4()), firebase_uid=uid,
                email=f"{uid}@simplesave.local", role=role,
                full_name=f"Dev {role.value.title()}", is_active=True,
            )
            session.add(existing)
        users[uid] = existing
    await session.flush()

    client = users["dev-client"]
    has_app = (await session.execute(
        select(Application).where(Application.client_user_id == client.id)
    )).scalars().first()
    if has_app:
        return  # demo application already present

    app_id = str(uuid.uuid4())
    session.add(Application(
        id=app_id,
        client_user_id=client.id,
        advisor_id=users["dev-advisor"].id,
        tier=TierEnum.online_guidance,
        status=ApplicationStatusEnum.personal_details_complete,
        loan_type=LoanTypeEnum.primary_residence,
        property_value="1500000",
        equity_amount="500000",
        loan_amount="1000000",
        financing_ratio="0.6667",
        max_loan_term_years=30,
        wizard_data={
            "loan_purpose": "primary_residence", "property_value": "1500000",
            "loan_amount": "1000000", "num_borrowers": 1, "first_home": True,
            "marital_status": "married", "total_monthly_income": "22000",
            "primary_borrower_birth_date": "1986-04-12",
        },
    ))
    session.add(Borrower(
        id=str(uuid.uuid4()), application_id=app_id, user_id=client.id,
        sequence_number=1, is_property_owner=True,
        first_name="יוסי", last_name="כהן", gender=GenderEnum.male,
        birth_date=_date(1986, 4, 12), marital_status=MaritalStatusEnum.married,
        num_children=2, education=EducationEnum.bachelor,
        phone="050-1234567", email="yossi@example.com",
        employment_status=EmploymentStatusEnum.employee, occupation="מהנדס תוכנה",
        employer_name="חברת הייטק בע\"מ", employer_city="תל אביב",
        employment_start_date=_date(2020, 3, 1), net_income="22000",
        address_city="תל אביב", address_street="הרצל", address_number="12", address_apartment="4",
        has_additional_citizenship=False, is_politically_exposed=False,
        has_health_issues=False, has_credit_issues=False,
        military_service_months=36, num_siblings_in_country=1,
    ))


async def main() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await seed_system_admin(session)
            await session.flush()   # ensure admin user row exists before FK refs
            await seed_banks(session)
            await seed_system_parameters(session)
            await seed_interest_rates(session)
            await seed_document_types(session)
            await seed_mixes(session)
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
