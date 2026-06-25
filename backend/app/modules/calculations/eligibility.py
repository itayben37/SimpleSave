"""
Vatikei HaAretz (Price for Residents) eligibility calculator.
spec: docs/specs/calculations/11-eligibility-calculator.md

6 scoring categories; max 100 points total.
Returns eligibility_score (0–100) and is_eligible (bool, threshold = 51).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


# ── Score table ───────────────────────────────────────────────────────────────
# Per spec 11-eligibility-calculator.md

MARITAL_STATUS_SCORES = {
    "single": 15,
    "married": 25,
    "divorced": 20,
    "widowed": 25,
}

# Children: 0 → 0pts, 1 → 5pts, 2 → 10pts, 3 → 15pts, 4+ → 20pts
def _children_score(count: int) -> int:
    if count == 0:
        return 0
    if count == 1:
        return 5
    if count == 2:
        return 10
    if count == 3:
        return 15
    return 20  # 4+

# Military service: none → 0, regular (36m+) → 10, reserve_100plus_days → 15
MILITARY_SCORES = {
    "none": 0,
    "regular": 10,
    "reserve_100plus_days": 15,
}

# Eligible siblings (brothers/sisters already received vatikei): 0 → 0, 1 → 5, 2+ → 10
def _siblings_score(count: int) -> int:
    if count == 0:
        return 0
    if count == 1:
        return 5
    return 10  # 2+

# Wedding duration years: < 2 → 0, 2–5 → 5, 6–10 → 10, 11–20 → 15, 21+ → 20
def _wedding_duration_score(years: int) -> int:
    if years < 2:
        return 0
    if years <= 5:
        return 5
    if years <= 10:
        return 10
    if years <= 20:
        return 15
    return 20  # 21+

# Age score: < 21 → 0, 21–29 → 5, 30–45 → 10, 46–60 → 5, 61+ → 0
def _age_score(age: int) -> int:
    if age < 21:
        return 0
    if age <= 29:
        return 5
    if age <= 45:
        return 10
    if age <= 60:
        return 5
    return 0


ELIGIBILITY_THRESHOLD = 51


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class EligibilityResult:
    eligibility_score: int
    is_eligible: bool
    score_breakdown: dict[str, int]   # category → points awarded


# ── Main calculator ───────────────────────────────────────────────────────────

def calculate_eligibility(
    marital_status: str,            # 'single' | 'married' | 'divorced' | 'widowed'
    number_of_children: int,
    military_service_type: str,     # 'none' | 'regular' | 'reserve_100plus_days'
    eligible_siblings_count: int,
    wedding_duration_years: int,    # 0 if not married/divorced/widowed
    applicant_birth_date: date,
    reference_date: date | None = None,
) -> EligibilityResult:
    ref = reference_date or date.today()
    age = (
        ref.year - applicant_birth_date.year
        - ((ref.month, ref.day) < (applicant_birth_date.month, applicant_birth_date.day))
    )

    breakdown = {
        "marital_status": MARITAL_STATUS_SCORES.get(marital_status, 0),
        "children": _children_score(max(0, number_of_children)),
        "military_service": MILITARY_SCORES.get(military_service_type, 0),
        "eligible_siblings": _siblings_score(max(0, eligible_siblings_count)),
        "wedding_duration": _wedding_duration_score(max(0, wedding_duration_years)),
        "age": _age_score(age),
    }

    total = sum(breakdown.values())
    return EligibilityResult(
        eligibility_score=total,
        is_eligible=total >= ELIGIBILITY_THRESHOLD,
        score_breakdown=breakdown,
    )
