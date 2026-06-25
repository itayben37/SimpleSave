"""Initial schema — all 18 entities per spec 02-data-model.md

Revision ID: 0001
Revises:
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    role_enum = sa.Enum("admin", "advisor", "client", name="roleenum")
    tier_enum = sa.Enum("mix_approval", "online_guidance", "personal_advisor", name="tierenum")
    application_status_enum = sa.Enum(
        "QUESTIONNAIRE_IN_PROGRESS", "QUESTIONNAIRE_COMPLETE", "REGISTERED", "TIER_SELECTED",
        "PERSONAL_DETAILS_COMPLETE", "AUTHORIZATION_SIGNED", "DOCUMENTS_SUBMITTED",
        "DOCUMENTS_APPROVED", "PRINCIPAL_APPROVAL_REQUESTED", "PRINCIPAL_APPROVAL_RECEIVED",
        "BANK_SELECTED", "MORTGAGE_SIGNED", "COLLATERALS_PENDING", "COLLATERALS_COMPLETE",
        "ACTIVE_MORTGAGE", name="applicationstatusenum",
    )
    loan_type_enum = sa.Enum("primary_residence", "additional_property", "all_purpose", "home_improvement", name="loantypeenum")
    property_source_enum = sa.Enum("contractor", "second_hand", "price_for_residents", "self_build", name="propertysourceenum")
    property_registration_enum = sa.Enum("tabu", "minha", "mishkenet", name="propertyregistrationenum")
    property_type_enum = sa.Enum("private_house", "duplex", "apartment_building", name="propertytypeenum")
    purchase_status_enum = sa.Enum("searching", "signed_contract", "about_to_sign", name="purchasestatusenum")
    money_needed_by_enum = sa.Enum("this_month", "two_months", "three_plus_months", name="moneyneededbyenum")
    willing_to_transfer_enum = sa.Enum("yes", "no", "want_details_first", name="willingtotransferenum")
    gender_enum = sa.Enum("male", "female", name="genderenum")
    marital_status_enum = sa.Enum("single", "married", "divorced", "widowed", name="maritalstatusenum")
    education_enum = sa.Enum("high_school", "post_secondary", "bachelor", "master", name="educationenum")
    employment_status_enum = sa.Enum("employee", "self_employed", "controlling_shareholder", name="employmentstatusenum")
    additional_income_type_enum = sa.Enum("pension", "rental", "dividend", "alimony_received", "other", name="additionalincometypeenum")
    fixed_expense_type_enum = sa.Enum("loan", "alimony_paid", "leasing", "rent", "other", name="fixedexpensetypeenum")
    expense_source_enum = sa.Enum("bank", "savings_fund", "insurance_company", "other", name="expensesourceenum")
    risk_level_enum = sa.Enum("low", "medium", "high", name="risklevelenum")
    track_type_enum = sa.Enum("fixed", "variable", "prime", name="tracktypeenum")
    amortization_type_enum = sa.Enum("spitzer", "equal_principal", name="amortizationtypeenum")
    loan_purpose_enum = sa.Enum("housing", "all_purpose", name="loanpurposeenum")
    principal_approval_status_enum = sa.Enum("pending", "approved", "rejected", "expired", name="principalapprovalstatusenum")
    document_status_enum = sa.Enum("required", "uploaded", "approved", "rejected", "not_required", name="documentstatusenum")
    collateral_status_enum = sa.Enum("pending", "submitted", "approved", name="collateralstatusenum")

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("firebase_uid", sa.String(128), unique=True, nullable=True),
        sa.Column("phone", sa.String(20), unique=True, nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # banks
    op.create_table(
        "banks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name_he", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("mortgage_hotline", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # mixes
    op.create_table(
        "mixes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("clock_number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # applications
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("client_user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("advisor_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tier", tier_enum, nullable=True),
        sa.Column("status", application_status_enum, nullable=False, server_default="QUESTIONNAIRE_IN_PROGRESS"),
        sa.Column("loan_type", loan_type_enum, nullable=True),
        sa.Column("property_source", property_source_enum, nullable=True),
        sa.Column("property_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("equity_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("equity_sources", JSONB, nullable=True),
        sa.Column("loan_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("financing_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("desired_monthly_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("desired_monthly_max", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_loan_term_years", sa.Integer, nullable=True),
        sa.Column("property_registration_type", property_registration_enum, nullable=True),
        sa.Column("property_type", property_type_enum, nullable=True),
        sa.Column("property_address_city", sa.String(100), nullable=True),
        sa.Column("property_address_street", sa.String(255), nullable=True),
        sa.Column("property_address_number", sa.String(20), nullable=True),
        sa.Column("property_address_apartment", sa.String(20), nullable=True),
        sa.Column("property_floor", sa.Integer, nullable=True),
        sa.Column("property_total_floors", sa.Integer, nullable=True),
        sa.Column("property_area_sqm", sa.Numeric(8, 2), nullable=True),
        sa.Column("property_age_years", sa.Integer, nullable=True),
        sa.Column("purchase_status", purchase_status_enum, nullable=True),
        sa.Column("contract_signed_date", sa.Date, nullable=True),
        sa.Column("money_needed_by", money_needed_by_enum, nullable=True),
        sa.Column("previously_applied_to_banks", sa.Boolean, nullable=True),
        sa.Column("previously_applied_bank_ids", JSONB, nullable=True),
        sa.Column("willing_to_transfer_account", willing_to_transfer_enum, nullable=True),
        sa.Column("has_prior_mortgage_application", sa.Boolean, nullable=True),
        sa.Column("selected_mix_id", UUID(as_uuid=False), sa.ForeignKey("mixes.id"), nullable=True),
        sa.Column("selected_bank_id", UUID(as_uuid=False), sa.ForeignKey("banks.id"), nullable=True),
        sa.Column("authorization_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # borrowers
    op.create_table(
        "borrowers",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_property_owner", sa.Boolean, nullable=False),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("gender", gender_enum, nullable=True),
        sa.Column("birth_date", sa.Date, nullable=True),
        sa.Column("marital_status", marital_status_enum, nullable=True),
        sa.Column("num_children", sa.Integer, nullable=True),
        sa.Column("children_shared", sa.Boolean, nullable=True),
        sa.Column("education", education_enum, nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("employment_status", employment_status_enum, nullable=True),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("employer_name", sa.String(255), nullable=True),
        sa.Column("employer_city", sa.String(100), nullable=True),
        sa.Column("employment_start_date", sa.Date, nullable=True),
        sa.Column("prev_employer_name", sa.String(255), nullable=True),
        sa.Column("prev_employment_start_date", sa.Date, nullable=True),
        sa.Column("prev_employment_end_date", sa.Date, nullable=True),
        sa.Column("has_additional_citizenship", sa.Boolean, nullable=True),
        sa.Column("has_foreign_tax_obligation", sa.Boolean, nullable=True),
        sa.Column("is_politically_exposed", sa.Boolean, nullable=True),
        sa.Column("has_health_issues", sa.Boolean, nullable=True),
        sa.Column("has_credit_issues", sa.Boolean, nullable=True),
        sa.Column("credit_issues_detail", sa.Text, nullable=True),
        sa.Column("net_income", sa.Numeric(12, 2), nullable=True),
        sa.Column("military_service_months", sa.Integer, nullable=True),
        sa.Column("num_siblings_in_country", sa.Integer, nullable=True),
        sa.Column("is_smoker", sa.Boolean, nullable=True),
        sa.Column("wedding_date", sa.Date, nullable=True),
        sa.Column("children_under_18", sa.Integer, nullable=True),
        sa.Column("address_city", sa.String(100), nullable=True),
        sa.Column("address_street", sa.String(255), nullable=True),
        sa.Column("address_number", sa.String(20), nullable=True),
        sa.Column("address_apartment", sa.String(20), nullable=True),
        sa.Column("has_checking_account", sa.Boolean, nullable=True),
        sa.Column("checking_accounts", JSONB, nullable=True),
        sa.Column("has_savings_fund", sa.Boolean, nullable=True),
        sa.Column("savings_fund_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("savings_fund_available_date", sa.Date, nullable=True),
        sa.Column("has_rental_payment", sa.Boolean, nullable=True),
        sa.Column("rental_payment_amount", sa.Numeric(12, 2), nullable=True),
    )

    # additional_incomes
    op.create_table(
        "additional_incomes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("borrower_id", UUID(as_uuid=False), sa.ForeignKey("borrowers.id"), nullable=False),
        sa.Column("income_type", additional_income_type_enum, nullable=False),
        sa.Column("income_type_detail", sa.String(255), nullable=True),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=False),
    )

    # fixed_expenses
    op.create_table(
        "fixed_expenses",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("borrower_id", UUID(as_uuid=False), sa.ForeignKey("borrowers.id"), nullable=False),
        sa.Column("expense_type", fixed_expense_type_enum, nullable=False),
        sa.Column("expense_type_detail", sa.String(255), nullable=True),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("interest_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("source", expense_source_enum, nullable=True),
    )

    # additional_properties
    op.create_table(
        "additional_properties",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("borrower_id", UUID(as_uuid=False), sa.ForeignKey("borrowers.id"), nullable=False),
        sa.Column("property_type", property_type_enum, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("street", sa.String(255), nullable=False),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("floor", sa.Integer, nullable=True),
        sa.Column("apartment_number", sa.String(20), nullable=True),
        sa.Column("area_sqm", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("existing_mortgage", sa.Numeric(14, 2), nullable=True),
    )

    # mix_tracks
    op.create_table(
        "mix_tracks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("mix_id", UUID(as_uuid=False), sa.ForeignKey("mixes.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("track_type", track_type_enum, nullable=False),
        sa.Column("cpi_linked", sa.Boolean, nullable=False),
        sa.Column("period_years", sa.Integer, nullable=False),
        sa.Column("rate_change_interval_months", sa.Integer, nullable=True),
        sa.Column("amortization_type", amortization_type_enum, nullable=False),
        sa.Column("percentage_of_mix", sa.Numeric(5, 2), nullable=False),
        sa.Column("anchor_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("spread", sa.Numeric(6, 4), nullable=True),
        sa.Column("total_rate", sa.Numeric(6, 4), nullable=True),
    )

    # interest_rate_table
    op.create_table(
        "interest_rate_table",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("track_type", track_type_enum, nullable=False),
        sa.Column("cpi_linked", sa.Boolean, nullable=False),
        sa.Column("loan_purpose", loan_purpose_enum, nullable=False),
        sa.Column("period_years_min", sa.Integer, nullable=False),
        sa.Column("period_years_max", sa.Integer, nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("created_by_admin_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    )

    # system_parameters
    op.create_table(
        "system_parameters",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Numeric(10, 6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_admin_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("previous_value", sa.Numeric(10, 6), nullable=True),
    )

    # document_types
    op.create_table(
        "document_types",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name_he", sa.String(255), nullable=False),
        sa.Column("description_he", sa.Text, nullable=True),
        sa.Column("required_condition", JSONB, nullable=False),
        sa.Column("required_for_principal_approval", sa.Boolean, nullable=False),
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("borrower_id", UUID(as_uuid=False), sa.ForeignKey("borrowers.id"), nullable=True),
        sa.Column("document_type_id", UUID(as_uuid=False), sa.ForeignKey("document_types.id"), nullable=True),
        sa.Column("manual_label", sa.String(255), nullable=True),
        sa.Column("is_required", sa.Boolean, nullable=False),
        sa.Column("required_for_principal_approval", sa.Boolean, nullable=False),
        sa.Column("status", document_status_enum, nullable=False, server_default="required"),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("is_required_for_approval", sa.Boolean, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # principal_approvals
    op.create_table(
        "principal_approvals",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("bank_id", UUID(as_uuid=False), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("status", principal_approval_status_enum, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("approved_mix_details", JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_best_offer", sa.Boolean, nullable=False, server_default="false"),
    )

    # collaterals
    op.create_table(
        "collaterals",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("description_he", sa.Text, nullable=False),
        sa.Column("status", collateral_status_enum, nullable=False, server_default="pending"),
        sa.Column("added_by_advisor_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("sender_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_url", sa.String(500), nullable=True),
        sa.Column("stage_tag", sa.String(100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("advisor_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # drawdowns
    op.create_table(
        "drawdowns",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("drawdown_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("mix_details", JSONB, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("alert_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=False), nullable=False),
        sa.Column("before_value", JSONB, nullable=True),
        sa.Column("after_value", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )

    # clock_results
    op.create_table(
        "clock_results",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=False), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("mix_id", UUID(as_uuid=False), sa.ForeignKey("mixes.id"), nullable=False),
        sa.Column("clock_number", sa.Integer, nullable=False),
        sa.Column("result_data", JSONB, nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Indexes for common query patterns
    op.create_index("ix_applications_client_user_id", "applications", ["client_user_id"])
    op.create_index("ix_applications_advisor_id", "applications", ["advisor_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_borrowers_application_id", "borrowers", ["application_id"])
    op.create_index("ix_documents_application_id", "documents", ["application_id"])
    op.create_index("ix_messages_application_id", "messages", ["application_id"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_clock_results_application_id", "clock_results", ["application_id"])
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])


def downgrade() -> None:
    op.drop_table("clock_results")
    op.drop_table("audit_logs")
    op.drop_table("drawdowns")
    op.drop_table("tasks")
    op.drop_table("messages")
    op.drop_table("collaterals")
    op.drop_table("principal_approvals")
    op.drop_table("documents")
    op.drop_table("document_types")
    op.drop_table("system_parameters")
    op.drop_table("interest_rate_table")
    op.drop_table("mix_tracks")
    op.drop_table("additional_properties")
    op.drop_table("fixed_expenses")
    op.drop_table("additional_incomes")
    op.drop_table("borrowers")
    op.drop_table("applications")
    op.drop_table("mixes")
    op.drop_table("banks")
    op.drop_table("users")

    for enum_name in [
        "roleenum", "tierenum", "applicationstatusenum", "loantypeenum", "propertysourceenum",
        "propertyregistrationenum", "propertytypeenum", "purchasestatusenum", "moneyneededbyenum",
        "willingtotransferenum", "genderenum", "maritalstatusenum", "educationenum",
        "employmentstatusenum", "additionalincometypeenum", "fixedexpensetypeenum",
        "expensesourceenum", "risklevelenum", "tracktypeenum", "amortizationtypeenum",
        "loanpurposeenum", "principalapprovalstatusenum", "documentstatusenum", "collateralstatusenum",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
