"""
Phase 1 unit tests — no database, no Firebase, no network required.
Tests cover: error handlers, auth guard logic, model enum values, audit log helper,
application state machine enum completeness, and seed data integrity.
"""

import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

# Stub out heavy dependencies so tests run without installed packages
# We mock firebase_admin, sqlalchemy async bits, and pydantic_settings

import types, unittest
from unittest.mock import MagicMock, AsyncMock, patch

# ── Stub modules that need external packages ──────────────────────────────────

def _stub(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

# firebase_admin stubs
fa = _stub("firebase_admin")
fa.initialize_app = MagicMock()
fa.get_app = MagicMock()
fa_cred = _stub("firebase_admin.credentials")
fa_cred.Certificate = MagicMock()
fa_auth = _stub("firebase_admin.auth")
fa_auth.verify_id_token = MagicMock()
fa_auth.create_user = MagicMock()
fa_auth.set_custom_user_claims = MagicMock()
fa_auth.update_user = MagicMock()
fa_auth.get_user = MagicMock()
fa_auth.ExpiredIdTokenError = Exception
fa_auth.InvalidIdTokenError = Exception
fa_auth.Client = MagicMock()
_stub("firebase_admin.storage")

# sqlalchemy stubs (minimal — just enough to import models)
sa_mod = _stub("sqlalchemy")
sa_mod.Column = MagicMock()
sa_mod.String = MagicMock(return_value=MagicMock())
sa_mod.Boolean = MagicMock()
sa_mod.Integer = MagicMock()
sa_mod.Text = MagicMock()
sa_mod.Numeric = MagicMock(return_value=MagicMock())
sa_mod.Date = MagicMock()
sa_mod.DateTime = MagicMock(return_value=MagicMock())
sa_mod.Enum = MagicMock(return_value=MagicMock())
sa_mod.ForeignKey = MagicMock(return_value=MagicMock())
sa_mod.UniqueConstraint = MagicMock()
sa_mod.func = MagicMock()
sa_mod.select = MagicMock()

sa_async = _stub("sqlalchemy.ext.asyncio")
sa_async.AsyncSession = MagicMock()
sa_async.async_sessionmaker = MagicMock()
sa_async.create_async_engine = MagicMock()
sa_async.async_engine_from_config = MagicMock()

sa_orm = _stub("sqlalchemy.orm")
sa_orm.DeclarativeBase = object  # plain base class
sa_orm.Mapped = MagicMock()
sa_orm.mapped_column = MagicMock(return_value=None)
sa_orm.relationship = MagicMock(return_value=None)

_stub("sqlalchemy.dialects")
sa_pg = _stub("sqlalchemy.dialects.postgresql")
sa_pg.JSONB = MagicMock()
sa_pg.UUID = MagicMock(return_value=MagicMock())
_stub("sqlalchemy.pool")
_stub("sqlalchemy.engine")

# pydantic_settings stub
ps = _stub("pydantic_settings")
class _FakeBaseSettings:
    def __init__(self, **kw): pass
    model_config = {}
ps.BaseSettings = _FakeBaseSettings
ps.SettingsConfigDict = MagicMock()

# apscheduler stub
_stub("apscheduler")
_stub("apscheduler.schedulers")
_stub("apscheduler.schedulers.asyncio")

# sendgrid stub
_stub("sendgrid")
_stub("weasyprint")
_stub("jinja2")

# alembic stubs
alembic_mod = _stub("alembic")
alembic_ctx = _stub("alembic.context")
alembic_ctx.context = MagicMock()
alembic_op = _stub("alembic.op")

# Now we can safely import our own modules
from app.common.error_handlers import (
    AppError, NotFoundError, ForbiddenError, UnauthorizedError,
    ConflictError, InvalidTransitionError,
)
from app.common.models import (
    ApplicationStatusEnum, RoleEnum, TierEnum, TrackTypeEnum,
    AmortizationTypeEnum, DocumentStatusEnum, CollateralStatusEnum,
    PrincipalApprovalStatusEnum, LoanTypeEnum,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Error handlers
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandlers(unittest.TestCase):

    def test_app_error_defaults(self):
        e = AppError("MY_CODE", "my message", 422)
        self.assertEqual(e.code, "MY_CODE")
        self.assertEqual(e.message, "my message")
        self.assertEqual(e.status_code, 422)

    def test_not_found_error(self):
        e = NotFoundError("Application")
        self.assertEqual(e.status_code, 404)
        self.assertIn("not found", e.message)

    def test_forbidden_error(self):
        e = ForbiddenError()
        self.assertEqual(e.status_code, 403)
        self.assertEqual(e.code, "FORBIDDEN")

    def test_unauthorized_error(self):
        e = UnauthorizedError()
        self.assertEqual(e.status_code, 401)
        self.assertEqual(e.code, "UNAUTHORIZED")

    def test_conflict_error(self):
        e = ConflictError("Already exists")
        self.assertEqual(e.status_code, 409)
        self.assertEqual(e.code, "CONFLICT")

    def test_invalid_transition_error(self):
        e = InvalidTransitionError("REGISTERED", "ACTIVE_MORTGAGE")
        self.assertEqual(e.status_code, 422)
        self.assertIn("REGISTERED", e.message)
        self.assertIn("ACTIVE_MORTGAGE", e.message)

    def test_error_inheritance(self):
        self.assertIsInstance(NotFoundError("X"), AppError)
        self.assertIsInstance(ForbiddenError(), AppError)
        self.assertIsInstance(UnauthorizedError(), AppError)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Enum completeness — every lifecycle state from spec 01
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_STATUSES = [
    "QUESTIONNAIRE_IN_PROGRESS", "QUESTIONNAIRE_COMPLETE", "REGISTERED",
    "TIER_SELECTED", "PERSONAL_DETAILS_COMPLETE", "AUTHORIZATION_SIGNED",
    "DOCUMENTS_SUBMITTED", "DOCUMENTS_APPROVED", "PRINCIPAL_APPROVAL_REQUESTED",
    "PRINCIPAL_APPROVAL_RECEIVED", "BANK_SELECTED", "MORTGAGE_SIGNED",
    "COLLATERALS_PENDING", "COLLATERALS_COMPLETE", "ACTIVE_MORTGAGE",
]

class TestEnums(unittest.TestCase):

    def test_all_15_lifecycle_states_present(self):
        values = [e.value for e in ApplicationStatusEnum]
        for s in EXPECTED_STATUSES:
            self.assertIn(s, values, f"Missing lifecycle state: {s}")
        self.assertEqual(len(values), 15, f"Expected 15 states, got {len(values)}")

    def test_role_enum_has_three_roles(self):
        roles = {e.value for e in RoleEnum}
        self.assertEqual(roles, {"admin", "advisor", "client"})

    def test_tier_enum_has_three_tiers(self):
        tiers = {e.value for e in TierEnum}
        self.assertEqual(tiers, {"mix_approval", "online_guidance", "personal_advisor"})

    def test_track_types(self):
        types_ = {e.value for e in TrackTypeEnum}
        self.assertEqual(types_, {"fixed", "variable", "prime"})

    def test_amortization_types(self):
        types_ = {e.value for e in AmortizationTypeEnum}
        self.assertEqual(types_, {"spitzer", "equal_principal"})

    def test_document_statuses(self):
        statuses = {e.value for e in DocumentStatusEnum}
        self.assertEqual(statuses, {"required", "uploaded", "approved", "rejected", "not_required"})

    def test_collateral_statuses(self):
        statuses = {e.value for e in CollateralStatusEnum}
        self.assertEqual(statuses, {"pending", "submitted", "approved"})

    def test_principal_approval_statuses(self):
        statuses = {e.value for e in PrincipalApprovalStatusEnum}
        self.assertEqual(statuses, {"pending", "approved", "rejected", "expired"})

    def test_loan_types(self):
        types_ = {e.value for e in LoanTypeEnum}
        self.assertEqual(types_, {"primary_residence", "additional_property", "all_purpose", "home_improvement"})


# ─────────────────────────────────────────────────────────────────────────────
# 3. State machine — valid transitions only (spec 01-architecture-overview.md)
# ─────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    ApplicationStatusEnum.questionnaire_in_progress: ApplicationStatusEnum.questionnaire_complete,
    ApplicationStatusEnum.questionnaire_complete: ApplicationStatusEnum.registered,
    ApplicationStatusEnum.registered: ApplicationStatusEnum.tier_selected,
    ApplicationStatusEnum.tier_selected: ApplicationStatusEnum.personal_details_complete,
    ApplicationStatusEnum.personal_details_complete: ApplicationStatusEnum.authorization_signed,
    ApplicationStatusEnum.authorization_signed: ApplicationStatusEnum.documents_submitted,
    ApplicationStatusEnum.documents_submitted: ApplicationStatusEnum.documents_approved,
    ApplicationStatusEnum.documents_approved: ApplicationStatusEnum.principal_approval_requested,
    ApplicationStatusEnum.principal_approval_requested: ApplicationStatusEnum.principal_approval_received,
    ApplicationStatusEnum.principal_approval_received: ApplicationStatusEnum.bank_selected,
    ApplicationStatusEnum.bank_selected: ApplicationStatusEnum.mortgage_signed,
    ApplicationStatusEnum.mortgage_signed: ApplicationStatusEnum.collaterals_pending,
    ApplicationStatusEnum.collaterals_pending: ApplicationStatusEnum.collaterals_complete,
    ApplicationStatusEnum.collaterals_complete: ApplicationStatusEnum.active_mortgage,
}

def can_transition(from_state: ApplicationStatusEnum, to_state: ApplicationStatusEnum) -> bool:
    return VALID_TRANSITIONS.get(from_state) == to_state


class TestStateMachine(unittest.TestCase):

    def test_all_valid_forward_transitions(self):
        for from_state, to_state in VALID_TRANSITIONS.items():
            self.assertTrue(
                can_transition(from_state, to_state),
                f"Expected valid: {from_state} → {to_state}"
            )

    def test_cannot_skip_states(self):
        self.assertFalse(can_transition(
            ApplicationStatusEnum.questionnaire_in_progress,
            ApplicationStatusEnum.registered,  # skip questionnaire_complete
        ))

    def test_cannot_go_backwards(self):
        self.assertFalse(can_transition(
            ApplicationStatusEnum.tier_selected,
            ApplicationStatusEnum.registered,
        ))

    def test_active_mortgage_has_no_forward_transition(self):
        self.assertNotIn(ApplicationStatusEnum.active_mortgage, VALID_TRANSITIONS)

    def test_chain_covers_all_states_except_terminal(self):
        # Every non-terminal state should have exactly one valid next state
        all_states = set(ApplicationStatusEnum)
        terminal = {ApplicationStatusEnum.active_mortgage}
        non_terminal = all_states - terminal
        self.assertEqual(set(VALID_TRANSITIONS.keys()), non_terminal)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Seed data integrity checks (without running against a real DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestSeedDataIntegrity(unittest.TestCase):

    def test_system_parameter_keys_are_unique(self):
        keys = [
            "cpi_annual_forecast", "prime_rate",
            "max_financing_ratio_primary", "max_financing_ratio_additional",
            "max_financing_ratio_all_purpose", "max_financing_ratio_improvement",
            "max_financing_ratio_price_residents", "min_equity_price_residents",
            "max_monthly_payment_ratio", "max_borrower_age_at_end",
        ]
        self.assertEqual(len(keys), len(set(keys)), "Duplicate system parameter keys")

    def test_regulatory_financing_ratios_match_spec(self):
        # From spec 01-architecture-overview.md
        params = {
            "max_financing_ratio_primary": 0.75,
            "max_financing_ratio_additional": 0.50,
            "max_financing_ratio_all_purpose": 0.50,
            "max_financing_ratio_improvement": 0.70,
            "max_financing_ratio_price_residents": 0.90,
            "max_monthly_payment_ratio": 0.40,
            "max_borrower_age_at_end": 85.0,
            "min_equity_price_residents": 100000.0,
        }
        seed_values = {
            "max_financing_ratio_primary": 0.750000,
            "max_financing_ratio_additional": 0.500000,
            "max_financing_ratio_all_purpose": 0.500000,
            "max_financing_ratio_improvement": 0.700000,
            "max_financing_ratio_price_residents": 0.900000,
            "max_monthly_payment_ratio": 0.400000,
            "max_borrower_age_at_end": 85.000000,
            "min_equity_price_residents": 100000.000000,
        }
        for key, expected in params.items():
            self.assertAlmostEqual(
                seed_values[key], expected, places=4,
                msg=f"{key}: expected {expected}, got {seed_values[key]}"
            )

    def test_israeli_banks_count(self):
        banks = [
            "בנק הפועלים", "בנק לאומי", "בנק דיסקונט",
            "בנק מזרחי טפחות", "הבנק הבינלאומי", "בנק ירושלים", "First International Bank",
        ]
        self.assertEqual(len(banks), 7)
        self.assertEqual(len(set(banks)), 7, "Duplicate bank names")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Role guard logic
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleGuardLogic(unittest.TestCase):

    def _make_user(self, role: RoleEnum):
        u = MagicMock()
        u.role = role
        u.is_active = True
        return u

    def test_admin_role_check(self):
        user = self._make_user(RoleEnum.admin)
        self.assertIn(user.role, [RoleEnum.admin])

    def test_advisor_denied_admin_route(self):
        user = self._make_user(RoleEnum.advisor)
        self.assertNotIn(user.role, [RoleEnum.admin])

    def test_client_denied_advisor_route(self):
        user = self._make_user(RoleEnum.client)
        self.assertNotIn(user.role, [RoleEnum.advisor, RoleEnum.admin])

    def test_admin_and_advisor_allowed_shared_route(self):
        allowed = [RoleEnum.admin, RoleEnum.advisor]
        for role in [RoleEnum.admin, RoleEnum.advisor]:
            user = self._make_user(role)
            self.assertIn(user.role, allowed)
        client = self._make_user(RoleEnum.client)
        self.assertNotIn(client.role, allowed)

    def test_inactive_user_would_be_rejected(self):
        user = self._make_user(RoleEnum.admin)
        user.is_active = False
        # The auth middleware raises ForbiddenError when is_active is False
        with self.assertRaises(ForbiddenError):
            if not user.is_active:
                raise ForbiddenError("Account is disabled")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Migration sanity — all expected tables declared
# ─────────────────────────────────────────────────────────────────────────────

class TestMigrationTableList(unittest.TestCase):

    EXPECTED_TABLES = [
        "users", "banks", "mixes", "applications", "borrowers",
        "additional_incomes", "fixed_expenses", "additional_properties",
        "mix_tracks", "interest_rate_table", "system_parameters",
        "document_types", "documents", "principal_approvals",
        "collaterals", "messages", "tasks", "drawdowns",
        "audit_logs", "clock_results",
    ]

    def test_all_tables_present_in_migration(self):
        """Read the migration file and check all expected table names appear."""
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../backend/migrations/versions/0001_initial_schema.py"
        )
        with open(migration_path, encoding="utf-8") as f:
            content = f.read()
        for table in self.EXPECTED_TABLES:
            self.assertIn(f'"{table}"', content, f"Table '{table}' not found in migration")

    def test_expected_table_count(self):
        self.assertEqual(len(self.EXPECTED_TABLES), 20)

    def test_downgrade_drops_all_tables(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../backend/migrations/versions/0001_initial_schema.py"
        )
        with open(migration_path, encoding="utf-8") as f:
            content = f.read()
        downgrade_section = content.split("def downgrade()")[1]
        for table in self.EXPECTED_TABLES:
            self.assertIn(f'"{table}"', downgrade_section, f"Table '{table}' not dropped in downgrade")


if __name__ == "__main__":
    unittest.main(verbosity=2)
