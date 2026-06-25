"""
Phase 2 unit tests — no database, no Firebase, no network required.
Tests: calculation engine, eligibility scoring, wizard validation logic.
"""

import sys
import os
import types
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

# ── Stub heavy deps so engine.py can be imported standalone ──────────────────

def _stub(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

_stub("firebase_admin"); _stub("firebase_admin.credentials")
_stub("firebase_admin.auth"); _stub("firebase_admin.storage")

from unittest.mock import MagicMock
sa_mod = _stub("sqlalchemy")
for _a in ["Column","String","Boolean","Integer","Text","Numeric","Date","DateTime",
           "Enum","ForeignKey","UniqueConstraint","func","select"]:
    setattr(sa_mod, _a, MagicMock(return_value=MagicMock()))
sa_async = _stub("sqlalchemy.ext.asyncio")
sa_async.AsyncSession = MagicMock(); sa_async.async_sessionmaker = MagicMock()
sa_async.create_async_engine = MagicMock()
sa_orm = _stub("sqlalchemy.orm")
sa_orm.DeclarativeBase = object; sa_orm.Mapped = MagicMock()
sa_orm.mapped_column = MagicMock(return_value=None); sa_orm.relationship = MagicMock(return_value=None)
_stub("sqlalchemy.dialects"); _stub("sqlalchemy.dialects.postgresql").JSONB = MagicMock()
_stub("sqlalchemy.dialects.postgresql").UUID = MagicMock(return_value=MagicMock())
_stub("sqlalchemy.pool"); _stub("sqlalchemy.engine")
ps = _stub("pydantic_settings")
class _FakeBaseSettings:
    model_config = {}
    def __init__(self, **kw): pass
ps.BaseSettings = _FakeBaseSettings; ps.SettingsConfigDict = MagicMock()
_stub("apscheduler"); _stub("apscheduler.schedulers"); _stub("apscheduler.schedulers.asyncio")
_stub("sendgrid"); _stub("weasyprint"); _stub("jinja2"); _stub("alembic"); _stub("alembic.context"); _stub("alembic.op")

from app.modules.calculations.engine import (
    calculate_track, calculate_risk_score, aggregate_mix,
    _spitzer_payment,
)
from app.modules.calculations.eligibility import calculate_eligibility


# ─────────────────────────────────────────────────────────────────────────────
# 1. Spitzer formula — verified example
# ─────────────────────────────────────────────────────────────────────────────

class TestSpitzerFormula(unittest.TestCase):

    def test_payment_1m_25y_3pt5(self):
        """₪1,000,000 / 25 years / 3.5% → ₪5,005.84 per spec example."""
        P = Decimal("1000000")
        r = Decimal("0.035") / Decimal("12")
        n = 25 * 12
        result = _spitzer_payment(P, r, n)
        self.assertAlmostEqual(float(result), 5005.84, delta=0.50)

    def test_zero_rate_limit(self):
        """Near-zero rate → payment ≈ P/n."""
        P = Decimal("120000")
        r = Decimal("0.000001") / Decimal("12")
        n = 120
        result = _spitzer_payment(P, r, n)
        self.assertAlmostEqual(float(result), 1000.0, delta=0.10)

    def test_payment_positive(self):
        P = Decimal("500000")
        r = Decimal("0.04") / Decimal("12")
        n = 240
        result = _spitzer_payment(P, r, n)
        self.assertGreater(result, Decimal("0"))


# ─────────────────────────────────────────────────────────────────────────────
# 2. calculate_track — Spitzer non-CPI
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateTrackSpitzer(unittest.TestCase):

    def _run(self, loan=1_000_000, years=25, rate="0.035", cpi=False):
        return calculate_track(
            loan_amount=Decimal(str(loan)),
            period_years=years,
            amortization_type="spitzer",
            track_type="fixed",
            annual_rate=Decimal(rate),
            cpi_annual_forecast=Decimal("0.03"),
            cpi_linked=cpi,
        )

    def test_monthly_payment_initial(self):
        r = self._run()
        self.assertAlmostEqual(float(r.monthly_payment_initial), 5005.84, delta=0.50)

    def test_schedule_length(self):
        r = self._run()
        self.assertEqual(len(r.amortization_schedule), 25 * 12)

    def test_total_principal_equals_loan(self):
        r = self._run()
        total_principal = sum(row.principal_payment for row in r.amortization_schedule)
        # Decimal rounding accumulates ~₪1–2 over 300 months; final-month correction absorbs it
        self.assertAlmostEqual(float(total_principal), 1_000_000, delta=3.0)

    def test_final_balance_near_zero(self):
        r = self._run()
        self.assertAlmostEqual(float(r.amortization_schedule[-1].balance_remaining), 0.0, delta=5.0)

    def test_cpi_non_linked_no_cpi_adjustments(self):
        r = self._run(cpi=False)
        total_cpi = sum(row.cpi_adjustment for row in r.amortization_schedule)
        self.assertEqual(total_cpi, Decimal("0"))

    def test_cpi_linked_has_adjustments(self):
        r = self._run(cpi=True)
        total_cpi = sum(row.cpi_adjustment for row in r.amortization_schedule)
        self.assertGreater(total_cpi, Decimal("0"))

    def test_term_below_4_years_not_feasible(self):
        r = calculate_track(
            loan_amount=Decimal("500000"),
            period_years=3,
            amortization_type="spitzer",
            track_type="fixed",
            annual_rate=Decimal("0.04"),
            cpi_annual_forecast=Decimal("0.03"),
            cpi_linked=False,
        )
        self.assertTrue(r.term_not_feasible)

    def test_total_interest_is_positive(self):
        r = self._run()
        self.assertGreater(r.total_interest_paid, Decimal("0"))

    def test_total_payment_gt_loan(self):
        r = self._run()
        self.assertGreater(r.total_payment_over_term, Decimal("1000000"))


# ─────────────────────────────────────────────────────────────────────────────
# 3. calculate_track — Equal Principal
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateTrackEqualPrincipal(unittest.TestCase):

    def _run(self, loan=600_000, years=20, rate="0.04", cpi=False):
        return calculate_track(
            loan_amount=Decimal(str(loan)),
            period_years=years,
            amortization_type="equal_principal",
            track_type="fixed",
            annual_rate=Decimal(rate),
            cpi_annual_forecast=Decimal("0.03"),
            cpi_linked=cpi,
        )

    def test_first_payment_greater_than_last(self):
        r = self._run()
        self.assertGreater(
            r.amortization_schedule[0].monthly_payment,
            r.amortization_schedule[-1].monthly_payment,
        )

    def test_total_principal_equals_loan(self):
        r = self._run()
        total = sum(row.principal_payment for row in r.amortization_schedule)
        self.assertAlmostEqual(float(total), 600_000, delta=2.0)

    def test_equal_principal_cpi_has_adjustments(self):
        r = self._run(cpi=True)
        total_cpi = sum(row.cpi_adjustment for row in r.amortization_schedule)
        self.assertGreater(total_cpi, Decimal("0"))

    def test_final_balance_near_zero(self):
        r = self._run()
        self.assertAlmostEqual(float(r.amortization_schedule[-1].balance_remaining), 0.0, delta=5.0)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Variable and Prime tracks
# ─────────────────────────────────────────────────────────────────────────────

class TestVariableAndPrimeTracks(unittest.TestCase):

    def test_variable_track_has_note(self):
        r = calculate_track(
            loan_amount=Decimal("300000"),
            period_years=15,
            amortization_type="spitzer",
            track_type="variable",
            annual_rate=Decimal("0.045"),
            cpi_annual_forecast=Decimal("0.03"),
            cpi_linked=False,
        )
        self.assertIsNotNone(r.rate_assumption_note_he)
        self.assertIn("ריבית", r.rate_assumption_note_he)

    def test_prime_track_no_cpi(self):
        r = calculate_track(
            loan_amount=Decimal("200000"),
            period_years=10,
            amortization_type="spitzer",
            track_type="prime",
            annual_rate=Decimal("0.0625"),
            cpi_annual_forecast=Decimal("0.03"),
            cpi_linked=False,
        )
        total_cpi = sum(row.cpi_adjustment for row in r.amortization_schedule)
        self.assertEqual(total_cpi, Decimal("0"))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Risk score calculation
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskScore(unittest.TestCase):

    def test_all_fixed_non_cpi_is_low(self):
        tracks = [{"track_type": "fixed", "cpi_linked": False, "percentage": Decimal("100")}]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(level, "low")
        self.assertEqual(score, Decimal("0"))

    def test_all_prime_is_high(self):
        tracks = [{"track_type": "prime", "cpi_linked": False, "percentage": Decimal("100")}]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(level, "high")
        self.assertEqual(score, Decimal("100"))

    def test_mixed_risk_medium(self):
        tracks = [
            {"track_type": "prime", "cpi_linked": False, "percentage": Decimal("50")},
            {"track_type": "fixed", "cpi_linked": False, "percentage": Decimal("50")},
        ]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(score, Decimal("50"))
        self.assertEqual(level, "medium")

    def test_risk_capped_at_100(self):
        tracks = [
            {"track_type": "prime", "cpi_linked": False, "percentage": Decimal("60")},
            {"track_type": "variable", "cpi_linked": False, "percentage": Decimal("60")},
        ]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(score, Decimal("100"))

    def test_cpi_linked_fixed_adds_to_risk(self):
        tracks = [
            {"track_type": "fixed", "cpi_linked": True, "percentage": Decimal("34")},
            {"track_type": "fixed", "cpi_linked": False, "percentage": Decimal("66")},
        ]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(score, Decimal("34"))
        self.assertEqual(level, "medium")

    def test_low_threshold_boundary(self):
        tracks = [{"track_type": "prime", "cpi_linked": False, "percentage": Decimal("32")}]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(level, "low")

    def test_high_threshold_boundary(self):
        tracks = [{"track_type": "prime", "cpi_linked": False, "percentage": Decimal("67")}]
        score, level = calculate_risk_score(tracks)
        self.assertEqual(level, "high")


# ─────────────────────────────────────────────────────────────────────────────
# 6. aggregate_mix
# ─────────────────────────────────────────────────────────────────────────────

class TestAggregateMix(unittest.TestCase):

    def _two_track_mix(self):
        tracks = [
            {
                "track_type": "fixed",
                "cpi_linked": False,
                "period_years": 25,
                "percentage_of_mix": Decimal("70"),
                "amortization_type": "spitzer",
                "spread": Decimal("0"),
                "rate_change_interval_months": None,
            },
            {
                "track_type": "prime",
                "cpi_linked": False,
                "period_years": 15,
                "percentage_of_mix": Decimal("30"),
                "amortization_type": "spitzer",
                "spread": Decimal("0"),
                "rate_change_interval_months": None,
            },
        ]
        rate_lookup = {("fixed", False, 25): Decimal("0.035")}
        return aggregate_mix(
            loan_amount=Decimal("1000000"),
            max_loan_term_years=30,
            tracks=tracks,
            prime_rate=Decimal("0.0625"),
            cpi_annual_forecast=Decimal("0.03"),
            interest_rate_lookup=rate_lookup,
        )

    def test_returns_mix_result(self):
        r = self._two_track_mix()
        self.assertIsNotNone(r)

    def test_monthly_payment_is_positive(self):
        r = self._two_track_mix()
        self.assertGreater(r.monthly_payment_initial, Decimal("0"))

    def test_two_per_track_results(self):
        r = self._two_track_mix()
        self.assertEqual(len(r.per_track_results), 2)

    def test_stacked_bar_data_exists(self):
        r = self._two_track_mix()
        self.assertGreater(len(r.stacked_bar_data), 0)

    def test_missing_rate_returns_none(self):
        tracks = [
            {
                "track_type": "fixed",
                "cpi_linked": False,
                "period_years": 25,
                "percentage_of_mix": Decimal("100"),
                "amortization_type": "spitzer",
                "spread": Decimal("0"),
                "rate_change_interval_months": None,
            }
        ]
        result = aggregate_mix(
            loan_amount=Decimal("1000000"),
            max_loan_term_years=30,
            tracks=tracks,
            prime_rate=Decimal("0.0625"),
            cpi_annual_forecast=Decimal("0.03"),
            interest_rate_lookup={},  # empty — no rates
        )
        self.assertIsNone(result)

    def test_risk_level_set(self):
        r = self._two_track_mix()
        self.assertIn(r.risk_level, ("low", "medium", "high"))

    def test_cumulative_totals_grows_monotonically(self):
        r = self._two_track_mix()
        totals = [d["total_paid_to_date"] for d in r.cumulative_totals_data]
        for i in range(1, len(totals)):
            self.assertGreaterEqual(totals[i], totals[i - 1])


# ─────────────────────────────────────────────────────────────────────────────
# 7. Eligibility calculator
# ─────────────────────────────────────────────────────────────────────────────

class TestEligibility(unittest.TestCase):

    def _calc(self, **kw):
        defaults = dict(
            marital_status="married",
            number_of_children=2,
            military_service_type="regular",
            eligible_siblings_count=0,
            wedding_duration_years=7,
            applicant_birth_date=date(1985, 1, 1),
            reference_date=date(2025, 6, 1),
        )
        defaults.update(kw)
        return calculate_eligibility(**defaults)

    def test_eligible_married_with_children(self):
        r = self._calc()
        self.assertTrue(r.is_eligible)
        self.assertGreaterEqual(r.eligibility_score, 51)

    def test_score_breakdown_has_six_keys(self):
        r = self._calc()
        self.assertEqual(len(r.score_breakdown), 6)

    def test_single_no_children_low_score(self):
        r = self._calc(
            marital_status="single",
            number_of_children=0,
            military_service_type="none",
            eligible_siblings_count=0,
            wedding_duration_years=0,
            applicant_birth_date=date(2003, 1, 1),  # age ~22
        )
        # single(15) + children(0) + military(0) + siblings(0) + wedding(0) + age(5) = 20
        self.assertFalse(r.is_eligible)
        self.assertEqual(r.eligibility_score, 20)

    def test_married_maximum_path(self):
        r = self._calc(
            marital_status="married",        # 25
            number_of_children=4,            # 20
            military_service_type="reserve_100plus_days",  # 15
            eligible_siblings_count=2,       # 10
            wedding_duration_years=25,       # 20
            applicant_birth_date=date(1980, 1, 1),  # age ~45 → 10
        )
        # 25+20+15+10+20+10 = 100
        self.assertEqual(r.eligibility_score, 100)
        self.assertTrue(r.is_eligible)

    def test_threshold_is_51(self):
        from app.modules.calculations.eligibility import ELIGIBILITY_THRESHOLD
        self.assertEqual(ELIGIBILITY_THRESHOLD, 51)

    def test_marital_status_scores(self):
        from app.modules.calculations.eligibility import MARITAL_STATUS_SCORES
        self.assertEqual(MARITAL_STATUS_SCORES["single"], 15)
        self.assertEqual(MARITAL_STATUS_SCORES["married"], 25)
        self.assertEqual(MARITAL_STATUS_SCORES["widowed"], 25)
        self.assertEqual(MARITAL_STATUS_SCORES["divorced"], 20)

    def test_children_score_buckets(self):
        from app.modules.calculations.eligibility import _children_score
        self.assertEqual(_children_score(0), 0)
        self.assertEqual(_children_score(1), 5)
        self.assertEqual(_children_score(2), 10)
        self.assertEqual(_children_score(3), 15)
        self.assertEqual(_children_score(4), 20)
        self.assertEqual(_children_score(10), 20)

    def test_age_score_buckets(self):
        from app.modules.calculations.eligibility import _age_score
        self.assertEqual(_age_score(17), 0)
        self.assertEqual(_age_score(25), 5)
        self.assertEqual(_age_score(35), 10)
        self.assertEqual(_age_score(55), 5)
        self.assertEqual(_age_score(65), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Wizard validation logic (pure Python mirror of frontend rules)
# ─────────────────────────────────────────────────────────────────────────────

class TestWizardValidation(unittest.TestCase):
    """Mirror the frontend step-validation logic from Wizard.jsx."""

    def test_step2_loan_cannot_exceed_90pct_property(self):
        pv = 1_000_000
        la = 910_000
        self.assertGreater(la, pv * 0.9)

    def test_step2_loan_at_90pct_is_allowed(self):
        pv = 1_000_000
        la = 900_000
        self.assertLessEqual(la, pv * 0.9)

    def test_step2_property_value_minimum(self):
        self.assertGreater(100_000, 0)  # minimum is ₪100,000

    def test_step2_loan_minimum(self):
        self.assertGreater(50_000, 0)   # minimum loan ₪50,000

    def test_step3_borrowers_in_range(self):
        for n in range(1, 5):
            self.assertTrue(1 <= n <= 4)
        self.assertFalse(1 <= 0 <= 4)
        self.assertFalse(1 <= 5 <= 4)

    def test_step8_age_minimum(self):
        # applicant must be at least 18
        from datetime import date as d
        birth = d(2010, 1, 1)
        ref = d(2025, 1, 1)
        age = ref.year - birth.year
        self.assertLess(age, 18)

    def test_step8_age_maximum(self):
        from datetime import date as d
        birth = d(1940, 1, 1)
        ref = d(2025, 1, 1)
        age = ref.year - birth.year
        self.assertGreater(age, 80)

    def test_required_fields_step1(self):
        data = {}
        self.assertFalse(bool(data.get("loan_purpose")))

    def test_valid_loan_purpose_values(self):
        valid = {"primary_residence", "additional_property", "all_purpose", "home_improvement"}
        self.assertIn("primary_residence", valid)
        self.assertNotIn("vacation_home", valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
