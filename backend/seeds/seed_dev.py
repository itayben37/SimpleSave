"""
Idempotent DEV/demo seeding for the AUTH_BYPASS sanity-check environment.

Run after the base seed (banks, params, rates, doc types, mixes):
    python -m seeds.seed_dev

Creates:
  - the three dev users (dev-client / dev-advisor / dev-admin) + the primary
    demo application (via seed_dev_data)
  - several extra clients & applications across the lifecycle, all assigned to
    dev-advisor, so the Advisor and Admin dashboards show real data
  - a handful of advisor tasks (some open, one overdue, one done)

Safe to run repeatedly: it keys off a marker and skips if already present.
"""

import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.common.models import (
    User, Application, Borrower, Task, RoleEnum,
    ApplicationStatusEnum, LoanTypeEnum, TierEnum,
    GenderEnum, MaritalStatusEnum, EducationEnum, EmploymentStatusEnum,
)
from seeds.seed_data import seed_dev_data


# (first, last, gender, birth, marital, employment, income, occupation,
#  status, tier, loan_type, property_value, equity, loan_amount)
_DEMO_CLIENTS = [
    ("דנה", "לוי", GenderEnum.female, date(1990, 7, 22), MaritalStatusEnum.single,
     EmploymentStatusEnum.employee, "18000", "מעצבת גרפית",
     ApplicationStatusEnum.questionnaire_in_progress, None,
     LoanTypeEnum.primary_residence, "1800000", "600000", "1200000"),
    ("משה", "ישראלי", GenderEnum.male, date(1982, 3, 5), MaritalStatusEnum.married,
     EmploymentStatusEnum.self_employed, "31000", "בעל עסק",
     ApplicationStatusEnum.tier_selected, TierEnum.mix_approval,
     LoanTypeEnum.primary_residence, "2400000", "900000", "1500000"),
    ("רונית", "בר", GenderEnum.female, date(1988, 11, 30), MaritalStatusEnum.married,
     EmploymentStatusEnum.employee, "24500", "אחות מוסמכת",
     ApplicationStatusEnum.documents_submitted, TierEnum.online_guidance,
     LoanTypeEnum.primary_residence, "2050000", "700000", "1350000"),
    ("אבי", "מזרחי", GenderEnum.male, date(1979, 1, 18), MaritalStatusEnum.married,
     EmploymentStatusEnum.controlling_shareholder, "42000", "מנכ\"ל חברה",
     ApplicationStatusEnum.principal_approval_received, TierEnum.personal_advisor,
     LoanTypeEnum.additional_property, "3200000", "1400000", "1800000"),
    ("שירה", "כהן", GenderEnum.female, date(1985, 6, 9), MaritalStatusEnum.married,
     EmploymentStatusEnum.employee, "27000", "עורכת דין",
     ApplicationStatusEnum.active_mortgage, TierEnum.personal_advisor,
     LoanTypeEnum.primary_residence, "2750000", "950000", "1800000"),
]

_MARKER_EMAIL = "dana.levi@demo.local"


async def seed_demo_clients(session: AsyncSession) -> None:
    advisor = (await session.execute(
        select(User).where(User.firebase_uid == "dev-advisor")
    )).scalar_one_or_none()
    if advisor is None:
        raise RuntimeError("dev-advisor user missing — run seed_dev_data first")

    # Idempotency marker
    exists = (await session.execute(
        select(Borrower).where(Borrower.email == _MARKER_EMAIL)
    )).scalars().first()
    if exists:
        print("Demo clients already seeded — skipping.")
        return

    for i, c in enumerate(_DEMO_CLIENTS):
        (first, last, gender, birth, marital, employment, income, occupation,
         status, tier, loan_type, prop_val, equity, loan_amt) = c

        # A lightweight client user per demo application
        client = User(
            id=str(uuid.uuid4()),
            firebase_uid=f"demo-client-{i}",
            email=f"{first}.{last}@demo.local".replace(" ", ""),
            role=RoleEnum.client,
            full_name=f"{first} {last}",
            is_active=True,
        )
        session.add(client)
        await session.flush()

        app_id = str(uuid.uuid4())
        ratio = round(float(loan_amt) / float(prop_val), 4)
        session.add(Application(
            id=app_id,
            client_user_id=client.id,
            advisor_id=advisor.id,
            tier=tier,
            status=status,
            loan_type=loan_type,
            property_value=prop_val,
            equity_amount=equity,
            loan_amount=loan_amt,
            financing_ratio=str(ratio),
            max_loan_term_years=30,
            wizard_data={
                "loan_purpose": loan_type.value,
                "property_value": prop_val,
                "loan_amount": loan_amt,
                "num_borrowers": 1,
                "marital_status": marital.value,
            },
        ))
        session.add(Borrower(
            id=str(uuid.uuid4()), application_id=app_id, user_id=client.id,
            sequence_number=1, is_property_owner=True,
            first_name=first, last_name=last, gender=gender,
            birth_date=birth, marital_status=marital,
            num_children=0 if marital == MaritalStatusEnum.single else 2,
            education=EducationEnum.bachelor,
            phone=f"05{i}-7654321",
            # First borrower carries the idempotency marker email
            email=_MARKER_EMAIL if i == 0 else f"{first}.{last}@demo.local".replace(" ", ""),
            employment_status=employment, occupation=occupation,
            employer_name="מעסיק לדוגמה", employer_city="תל אביב",
            employment_start_date=date(2019, 1, 1), net_income=income,
            address_city="תל אביב", address_street="דיזנגוף",
            address_number=str(10 + i),
            has_additional_citizenship=False, is_politically_exposed=False,
            has_health_issues=False, has_credit_issues=False,
        ))

    # Advisor tasks
    today = date.today()
    tasks = [
        ("להתקשר ללקוחה דנה לוי לתיאום פגישה", today + timedelta(days=1), False),
        ("לבדוק מסמכים שהועלו ע\"י רונית בר", today + timedelta(days=2), False),
        ("להכין בקשת אישור עקרוני לאבי מזרחי", today - timedelta(days=1), False),
        ("לשלוח תמהיל מעודכן למשה ישראלי", today + timedelta(days=4), False),
        ("לסגור תיק משכנתא של שירה כהן", today - timedelta(days=3), True),
    ]
    for title, due, done in tasks:
        session.add(Task(
            id=str(uuid.uuid4()), advisor_id=advisor.id,
            title=title, due_date=due, is_complete=done,
        ))

    print(f"Seeded {len(_DEMO_CLIENTS)} demo clients + {len(tasks)} advisor tasks.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_dev_data(session)
        await seed_demo_clients(session)
        await session.commit()
    print("Dev seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
