"""
SQLAlchemy ORM models for all 18 entities defined in docs/specs/system/02-data-model.md.
Firebase Auth owns OTP/session state — those tables are not included here.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

# ---------------------------------------------------------------------------
# Enums (mirroring spec exactly)
# ---------------------------------------------------------------------------

import enum as pyenum


class RoleEnum(str, pyenum.Enum):
    admin = "admin"
    advisor = "advisor"
    client = "client"


class TierEnum(str, pyenum.Enum):
    mix_approval = "mix_approval"
    online_guidance = "online_guidance"
    personal_advisor = "personal_advisor"


class ApplicationStatusEnum(str, pyenum.Enum):
    questionnaire_in_progress = "QUESTIONNAIRE_IN_PROGRESS"
    questionnaire_complete = "QUESTIONNAIRE_COMPLETE"
    registered = "REGISTERED"
    tier_selected = "TIER_SELECTED"
    personal_details_complete = "PERSONAL_DETAILS_COMPLETE"
    authorization_signed = "AUTHORIZATION_SIGNED"
    documents_submitted = "DOCUMENTS_SUBMITTED"
    documents_approved = "DOCUMENTS_APPROVED"
    principal_approval_requested = "PRINCIPAL_APPROVAL_REQUESTED"
    principal_approval_received = "PRINCIPAL_APPROVAL_RECEIVED"
    bank_selected = "BANK_SELECTED"
    mortgage_signed = "MORTGAGE_SIGNED"
    collaterals_pending = "COLLATERALS_PENDING"
    collaterals_complete = "COLLATERALS_COMPLETE"
    active_mortgage = "ACTIVE_MORTGAGE"


class LoanTypeEnum(str, pyenum.Enum):
    primary_residence = "primary_residence"
    additional_property = "additional_property"
    all_purpose = "all_purpose"
    home_improvement = "home_improvement"


class PropertySourceEnum(str, pyenum.Enum):
    contractor = "contractor"
    second_hand = "second_hand"
    price_for_residents = "price_for_residents"
    self_build = "self_build"


class PropertyRegistrationEnum(str, pyenum.Enum):
    tabu = "tabu"
    minha = "minha"
    mishkenet = "mishkenet"


class PropertyTypeEnum(str, pyenum.Enum):
    private_house = "private_house"
    duplex = "duplex"
    apartment_building = "apartment_building"


class PurchaseStatusEnum(str, pyenum.Enum):
    searching = "searching"
    signed_contract = "signed_contract"
    about_to_sign = "about_to_sign"


class MoneyNeededByEnum(str, pyenum.Enum):
    this_month = "this_month"
    two_months = "two_months"
    three_plus_months = "three_plus_months"


class WillingToTransferEnum(str, pyenum.Enum):
    yes = "yes"
    no = "no"
    want_details_first = "want_details_first"


class GenderEnum(str, pyenum.Enum):
    male = "male"
    female = "female"


class MaritalStatusEnum(str, pyenum.Enum):
    single = "single"
    married = "married"
    divorced = "divorced"
    widowed = "widowed"


class EducationEnum(str, pyenum.Enum):
    high_school = "high_school"
    post_secondary = "post_secondary"
    bachelor = "bachelor"
    master = "master"


class EmploymentStatusEnum(str, pyenum.Enum):
    employee = "employee"
    self_employed = "self_employed"
    controlling_shareholder = "controlling_shareholder"


class AdditionalIncomeTypeEnum(str, pyenum.Enum):
    pension = "pension"
    rental = "rental"
    dividend = "dividend"
    alimony_received = "alimony_received"
    other = "other"


class FixedExpenseTypeEnum(str, pyenum.Enum):
    loan = "loan"
    alimony_paid = "alimony_paid"
    leasing = "leasing"
    rent = "rent"
    other = "other"


class ExpenseSourceEnum(str, pyenum.Enum):
    bank = "bank"
    savings_fund = "savings_fund"
    insurance_company = "insurance_company"
    other = "other"


class RiskLevelEnum(str, pyenum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TrackTypeEnum(str, pyenum.Enum):
    fixed = "fixed"
    variable = "variable"
    prime = "prime"


class AmortizationTypeEnum(str, pyenum.Enum):
    spitzer = "spitzer"
    equal_principal = "equal_principal"


class LoanPurposeEnum(str, pyenum.Enum):
    housing = "housing"
    all_purpose = "all_purpose"


class PrincipalApprovalStatusEnum(str, pyenum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class DocumentStatusEnum(str, pyenum.Enum):
    required = "required"
    uploaded = "uploaded"
    approved = "approved"
    rejected = "rejected"
    not_required = "not_required"


class CollateralStatusEnum(str, pyenum.Enum):
    pending = "pending"
    submitted = "submitted"
    approved = "approved"


# ---------------------------------------------------------------------------
# Helper for UUID primary keys
# ---------------------------------------------------------------------------

def new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Entity: User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    applications_as_client: Mapped[list["Application"]] = relationship(
        "Application", foreign_keys="Application.client_user_id", back_populates="client"
    )
    applications_as_advisor: Mapped[list["Application"]] = relationship(
        "Application", foreign_keys="Application.advisor_id", back_populates="advisor"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="actor")


# ---------------------------------------------------------------------------
# Entity: Application
# ---------------------------------------------------------------------------

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    client_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    advisor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    tier: Mapped[TierEnum | None] = mapped_column(Enum(TierEnum), nullable=True)
    status: Mapped[ApplicationStatusEnum] = mapped_column(
        Enum(ApplicationStatusEnum), nullable=False,
        default=ApplicationStatusEnum.questionnaire_in_progress,
    )
    loan_type: Mapped[LoanTypeEnum | None] = mapped_column(Enum(LoanTypeEnum), nullable=True)
    property_source: Mapped[PropertySourceEnum | None] = mapped_column(Enum(PropertySourceEnum), nullable=True)
    property_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    equity_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    equity_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    loan_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    financing_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    desired_monthly_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    desired_monthly_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_loan_term_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_registration_type: Mapped[PropertyRegistrationEnum | None] = mapped_column(Enum(PropertyRegistrationEnum), nullable=True)
    property_type: Mapped[PropertyTypeEnum | None] = mapped_column(Enum(PropertyTypeEnum), nullable=True)
    property_address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_address_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_address_apartment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    property_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_status: Mapped[PurchaseStatusEnum | None] = mapped_column(Enum(PurchaseStatusEnum), nullable=True)
    contract_signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    money_needed_by: Mapped[MoneyNeededByEnum | None] = mapped_column(Enum(MoneyNeededByEnum), nullable=True)
    previously_applied_to_banks: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    previously_applied_bank_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    willing_to_transfer_account: Mapped[WillingToTransferEnum | None] = mapped_column(Enum(WillingToTransferEnum), nullable=True)
    has_prior_mortgage_application: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    selected_mix_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("mixes.id"), nullable=True)
    selected_bank_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("banks.id"), nullable=True)
    authorization_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["User"] = relationship("User", foreign_keys=[client_user_id], back_populates="applications_as_client")
    advisor: Mapped["User | None"] = relationship("User", foreign_keys=[advisor_id], back_populates="applications_as_advisor")
    borrowers: Mapped[list["Borrower"]] = relationship("Borrower", back_populates="application", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="application")
    principal_approvals: Mapped[list["PrincipalApproval"]] = relationship("PrincipalApproval", back_populates="application")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="application")
    collaterals: Mapped[list["Collateral"]] = relationship("Collateral", back_populates="application")
    drawdowns: Mapped[list["Drawdown"]] = relationship("Drawdown", back_populates="application")
    selected_mix: Mapped["Mix | None"] = relationship("Mix", foreign_keys=[selected_mix_id])
    selected_bank: Mapped["Bank | None"] = relationship("Bank", foreign_keys=[selected_bank_id])


# ---------------------------------------------------------------------------
# Entity: Borrower
# ---------------------------------------------------------------------------

class Borrower(Base):
    __tablename__ = "borrowers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    is_property_owner: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[GenderEnum | None] = mapped_column(Enum(GenderEnum), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    marital_status: Mapped[MaritalStatusEnum | None] = mapped_column(Enum(MaritalStatusEnum), nullable=True)
    num_children: Mapped[int | None] = mapped_column(Integer, nullable=True)
    children_shared: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    education: Mapped[EducationEnum | None] = mapped_column(Enum(EducationEnum), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_status: Mapped[EmploymentStatusEnum | None] = mapped_column(Enum(EmploymentStatusEnum), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employer_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employment_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prev_employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prev_employment_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prev_employment_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    has_additional_citizenship: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_foreign_tax_obligation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_politically_exposed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_health_issues: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_credit_issues: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    credit_issues_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    military_service_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_siblings_in_country: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_smoker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    wedding_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    children_under_18: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_apartment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    has_checking_account: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    checking_accounts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    has_savings_fund: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    savings_fund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    savings_fund_available_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    has_rental_payment: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rental_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    application: Mapped["Application"] = relationship("Application", back_populates="borrowers")
    additional_incomes: Mapped[list["AdditionalIncome"]] = relationship("AdditionalIncome", back_populates="borrower", cascade="all, delete-orphan")
    fixed_expenses: Mapped[list["FixedExpense"]] = relationship("FixedExpense", back_populates="borrower", cascade="all, delete-orphan")
    additional_properties: Mapped[list["AdditionalProperty"]] = relationship("AdditionalProperty", back_populates="borrower", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="borrower")


# ---------------------------------------------------------------------------
# Entity: AdditionalIncome
# ---------------------------------------------------------------------------

class AdditionalIncome(Base):
    __tablename__ = "additional_incomes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    borrower_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("borrowers.id"), nullable=False)
    income_type: Mapped[AdditionalIncomeTypeEnum] = mapped_column(Enum(AdditionalIncomeTypeEnum), nullable=False)
    income_type_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="additional_incomes")


# ---------------------------------------------------------------------------
# Entity: FixedExpense
# ---------------------------------------------------------------------------

class FixedExpense(Base):
    __tablename__ = "fixed_expenses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    borrower_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("borrowers.id"), nullable=False)
    expense_type: Mapped[FixedExpenseTypeEnum] = mapped_column(Enum(FixedExpenseTypeEnum), nullable=False)
    expense_type_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remaining_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    source: Mapped[ExpenseSourceEnum | None] = mapped_column(Enum(ExpenseSourceEnum), nullable=True)

    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="fixed_expenses")


# ---------------------------------------------------------------------------
# Entity: AdditionalProperty
# ---------------------------------------------------------------------------

class AdditionalProperty(Base):
    __tablename__ = "additional_properties"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    borrower_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("borrowers.id"), nullable=False)
    property_type: Mapped[PropertyTypeEnum] = mapped_column(Enum(PropertyTypeEnum), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    apartment_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    existing_mortgage: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="additional_properties")


# ---------------------------------------------------------------------------
# Entity: Mix
# ---------------------------------------------------------------------------

class Mix(Base):
    __tablename__ = "mixes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    clock_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[RiskLevelEnum] = mapped_column(Enum(RiskLevelEnum), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tracks: Mapped[list["MixTrack"]] = relationship("MixTrack", back_populates="mix", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Entity: MixTrack
# ---------------------------------------------------------------------------

class MixTrack(Base):
    __tablename__ = "mix_tracks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    mix_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("mixes.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    track_type: Mapped[TrackTypeEnum] = mapped_column(Enum(TrackTypeEnum), nullable=False)
    cpi_linked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    period_years: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_change_interval_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amortization_type: Mapped[AmortizationTypeEnum] = mapped_column(Enum(AmortizationTypeEnum), nullable=False)
    percentage_of_mix: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    anchor_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    spread: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    mix: Mapped["Mix"] = relationship("Mix", back_populates="tracks")


# ---------------------------------------------------------------------------
# Entity: InterestRateTable
# ---------------------------------------------------------------------------

class InterestRateTable(Base):
    __tablename__ = "interest_rate_table"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    track_type: Mapped[TrackTypeEnum] = mapped_column(Enum(TrackTypeEnum), nullable=False)
    cpi_linked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    loan_purpose: Mapped[LoanPurposeEnum] = mapped_column(Enum(LoanPurposeEnum), nullable=False)
    period_years_min: Mapped[int] = mapped_column(Integer, nullable=False)
    period_years_max: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_admin_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)


# ---------------------------------------------------------------------------
# Entity: SystemParameter
# ---------------------------------------------------------------------------

class SystemParameter(Base):
    __tablename__ = "system_parameters"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by_admin_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    previous_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)


# ---------------------------------------------------------------------------
# Entity: Bank
# ---------------------------------------------------------------------------

class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name_he: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mortgage_hotline: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ---------------------------------------------------------------------------
# Entity: PrincipalApproval
# ---------------------------------------------------------------------------

class PrincipalApproval(Base):
    __tablename__ = "principal_approvals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    bank_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("banks.id"), nullable=False)
    status: Mapped[PrincipalApprovalStatusEnum] = mapped_column(Enum(PrincipalApprovalStatusEnum), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    approved_mix_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_best_offer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    application: Mapped["Application"] = relationship("Application", back_populates="principal_approvals")
    bank: Mapped["Bank"] = relationship("Bank")


# ---------------------------------------------------------------------------
# Entity: DocumentType
# ---------------------------------------------------------------------------

class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name_he: Mapped[str] = mapped_column(String(255), nullable=False)
    description_he: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    required_for_principal_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ---------------------------------------------------------------------------
# Entity: Document
# ---------------------------------------------------------------------------

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    borrower_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("borrowers.id"), nullable=True)
    document_type_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("document_types.id"), nullable=True)
    manual_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    required_for_principal_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[DocumentStatusEnum] = mapped_column(Enum(DocumentStatusEnum), nullable=False, default=DocumentStatusEnum.required)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required_for_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    application: Mapped["Application"] = relationship("Application", back_populates="documents")
    borrower: Mapped["Borrower | None"] = relationship("Borrower", back_populates="documents")
    document_type: Mapped["DocumentType | None"] = relationship("DocumentType")


# ---------------------------------------------------------------------------
# Entity: Collateral
# ---------------------------------------------------------------------------

class Collateral(Base):
    __tablename__ = "collaterals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    description_he: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CollateralStatusEnum] = mapped_column(Enum(CollateralStatusEnum), nullable=False, default=CollateralStatusEnum.pending)
    added_by_advisor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    application: Mapped["Application"] = relationship("Application", back_populates="collaterals")


# ---------------------------------------------------------------------------
# Entity: Message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    sender_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stage_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship("Application", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])


# ---------------------------------------------------------------------------
# Entity: Task
# ---------------------------------------------------------------------------

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    advisor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    application_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    advisor: Mapped["User"] = relationship("User", foreign_keys=[advisor_id])


# ---------------------------------------------------------------------------
# Entity: Drawdown
# ---------------------------------------------------------------------------

class Drawdown(Base):
    __tablename__ = "drawdowns"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    drawdown_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    mix_details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship("Application", back_populates="drawdowns")


# ---------------------------------------------------------------------------
# Entity: AuditLog
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    actor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    before_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    actor: Mapped["User"] = relationship("User", back_populates="audit_logs")


# ---------------------------------------------------------------------------
# Entity: ClockResult (cache table — spec 10-clocks-mix-generation.md)
# ---------------------------------------------------------------------------

class ClockResult(Base):
    __tablename__ = "clock_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    mix_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("mixes.id"), nullable=False)
    clock_number: Mapped[int] = mapped_column(Integer, nullable=False)
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    application: Mapped["Application"] = relationship("Application")
    mix: Mapped["Mix"] = relationship("Mix")
