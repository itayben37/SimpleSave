<!-- /autoplan restore point: /Users/giladshekalim/.gstack/projects/GiladShekalim-SimpleSave/main-autoplan-restore-20260625-215941.md -->
# SimpleSave — Implementation Plan

## Problem Statement

Mortgage advisors in Israel manage their clients through a fragmented mix of WhatsApp messages, Google Sheets, and email. Clients have no visibility into their process and advisors have no tooling to scale beyond 10 clients. SimpleSave replaces this with a structured B2B2C platform: clients self-serve through a guided mortgage wizard, advisors manage their caseload in one dashboard, and the admin controls pricing, mixes, and rate parameters.

## What We Are Building

A full-stack Hebrew-language (RTL) web application with:
- 3 roles: Admin, Advisor, Client
- 3 service tiers: Tier 1 (self-service), Tier 2 (async advisor), Tier 3 (dedicated advisor + calendar)
- OTP-only auth (phone or email), no passwords
- 15-state application lifecycle (questionnaire → active mortgage)
- Mortgage mix calculator with 5 "clocks" (Chart.js), Spitzer and Keren Shava amortization
- Server-side PDF generation (authorization letters), dynamic document list per borrower profile
- Israeli Privacy Protection Law Standard 13 compliance (AES-256 at rest, TLS 1.3)

**Out of scope v1:** refinancing, mortgage insurance, payment processing, e-signature, AI document validation.

## Specs Reference

All 50 spec files live in `docs/specs/`. Implementation must match spec exactly.
Key files:
- `system/01-architecture-overview.md` — SOLID principles, state machine, non-functionals
- `system/02-data-model.md` — all DB entities and relationships
- `calculations/09-mortgage-calculation-engine.md` — Spitzer/Keren Shava formulas
- `calculations/10-clocks-mix-generation.md` — 5-clock orchestration
- `flows/17-flow-new-mortgage-questionnaire.md` — 10-question wizard
- `screens/31-screen-personal-details.md` through `screens/36-screen-post-mortgage-dashboard.md` — all client screens

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript | SSR for SEO on home/clocks, RTL-ready, strong ecosystem |
| Styling | Tailwind CSS + custom RTL config | Utility-first, dark admin theme easy with CSS vars |
| State | Zustand | Lightweight, no boilerplate, works with Next.js App Router |
| Backend | Node.js + Express (or Fastify) + TypeScript | Team familiarity, fast iteration |
| ORM | Prisma | Type-safe, migrations, PostgreSQL support |
| Database | PostgreSQL | Relational integrity, JSONB for flexible doc metadata |
| File storage | AWS S3 (or compatible) | Document uploads, PDF storage |
| OTP | Twilio (SMS) + SendGrid (email) — pluggable interface | Swappable per spec |
| PDF | Puppeteer (server-side) | As specified in 06-pdf-generation.md |
| Charts | Chart.js | Confirmed from spec reference HTML |
| Auth | JWT (24h sliding window) + OTP flow | Per 03-authentication.md |
| Calendar | Custom slots (v1), consider Cal.com for v2 | Tier 3 booking only |

## Build Phases

### Phase 1 — Foundation (Weeks 1–3)
**Goal:** working repo, DB schema, auth, and skeleton routes. Nothing renders yet — backend only.

**Deliverables:**
1. Monorepo structure: `src/frontend/`, `src/backend/`, `src/database/`, `tests/`, `infrastructure/`
2. PostgreSQL schema via Prisma migrations for all 18 entities (spec `02-data-model.md`)
3. Seed data: banks, cities, document types, default SystemParameters, InterestRateTable initial values
4. OTP auth flow: send OTP → verify → JWT session (spec `03-authentication.md`). 5-attempt lockout, 24h expiry.
5. User creation on first OTP verify (auto-register)
6. Role middleware: ADMIN / ADVISOR / CLIENT guard on all routes
7. Audit log middleware: writes AuditLog entry on every state-changing POST/PATCH/DELETE
8. Base Next.js project: RTL config, Hebrew font (Heebo), Tailwind dark + light themes, CSS variables matching admin reference UI (`--bg:#0f1623`, `--accent:#3b82f6`)

**Success criteria:** `POST /auth/otp/send` + `POST /auth/otp/verify` returns JWT. DB migrations run clean. Role guard returns 403 for wrong role.

---

### Phase 2 — Questionnaire + Clocks (Weeks 4–6)
**Goal:** the full guest + client experience up to tier selection, including the mortgage calculator.

**Deliverables:**
1. 10-question mortgage wizard (spec `screens/27`, `flows/17`):
   - All question types, conditional logic, auto-save to sessionStorage (pre-auth)
   - Post-Q10 OTP registration gate
   - Data migration from sessionStorage → DB on registration
2. Mortgage calculation engine (spec `09-mortgage-calculation-engine.md`):
   - Spitzer amortization formula, Keren Shava, CPI linkage, prime track
   - All rounding rules
   - Unit-tested: worked example ₪1M / 25y / 3.5% = ₪5,005.84/month
3. Clocks/mix generation (spec `10-clocks-mix-generation.md`):
   - Admin-configured mixes → 5 clock results
   - `clock_results` cache table, recalculation on SystemParameter change
   - Risk speedometer (score formula)
4. Clocks screen (spec `screens/28`): 5 cards, Chart.js drill-down (monthly/cumulative), risk needle
5. Eligibility calculator (spec `11-eligibility-calculator.md`): vatikei haaretz scoring
6. OTP registration screen (spec `screens/29`)
7. Tier selection screen (spec `screens/46`): display-only, no payment

**Success criteria:** Guest completes wizard, registers, sees 5 clocks with correct amortization values. Calculation matches manual formula verification.

---

### Phase 3 — Personal Area: Client Flow (Weeks 7–10)
**Goal:** full client lifecycle from TIER_SELECTED → DOCUMENTS_SUBMITTED.

**Deliverables:**
1. Application state machine enforcement: transitions only via service layer, unidirectional
2. Personal Area Hub (spec `screens/30`): 7-tab shell, lock state matrix per tier × lifecycle
3. Personal Details (spec `screens/31`): all 18+ borrower fields, multi-borrower sub-tabs, auto-save, eligibility widget
4. Mortgage Details (spec `screens/32`): financing ratio live validation, equity sources, payment cap logic
5. Document management system (spec `05-document-management.md`, `screens/33`):
   - Dynamic doc list generation per borrower profile
   - S3 upload with size/format validation (10MB, PDF/JPG/PNG)
   - PDF.js viewer modal
   - Progress gate bar
6. PDF generation (spec `06-pdf-generation.md`): authorization letter generation per bank, Handlebars templates, batch download
7. Email engine (spec `07-email-engine.md`): 15 templates, pluggable provider interface, delivery tracking
8. Notification triggers for all 15 notification events (spec `04-notification-system.md`)

**Success criteria:** Client fills personal details, uploads all required docs, downloads signed authorization letters. State advances to DOCUMENTS_SUBMITTED. All notifications fire.

---

### Phase 4 — Advisor Area + Principal Approval (Weeks 11–14)
**Goal:** advisor manages clients, approves docs, enters bank responses.

**Deliverables:**
1. Advisor dashboard (spec `screens/44`): My Clients tab (sorted by next action + unread messages), Tasks tab
2. Advisor client detail (spec `screens/45`): full 6-tab mirror of client view with edit rights, approve/reject documents, state transition controls
3. Document review flow: advisor approve/reject per document, rejection reason, re-upload loop
4. Admin client management (spec `screens/42`): leads table, assign advisor modal
5. Admin advisors management (spec `screens/43`): add/deactivate advisors, bulk reassign
6. Bank response entry: principal approval received → entered by advisor, best offer computation
7. Principal approval screen (spec `screens/34`): bank card grid, best offer badge, 2-step bank selection
8. Advisor messages / two-way chat (spec `screens/37`): Tier 2/3 message threads, stage tags, read receipts
9. Tier 3 calendar booking (spec `screens/47`): weekly slot grid, booking/cancel/reschedule, 24h/1h reminders

**Success criteria:** Advisor assigns leads, approves docs, enters bank approvals. Client selects bank. State reaches BANK_SELECTED.

---

### Phase 5 — Admin Dashboard + Post-Mortgage (Weeks 15–17)
**Goal:** admin controls all parameters, client tracks active mortgage.

**Deliverables:**
1. Admin overview dashboard (spec `screens/38`): summary cards, audit feed, unassigned queue
2. Admin mix manager (spec `screens/39`): inline track editing, 100% validation, Recalculate All
3. Admin interest rates (spec `screens/40`): dual housing/all-purpose tables
4. Admin parameters (spec `screens/41`): CPI, prime, anchors, change log
5. Collaterals screen (spec `screens/35`): advisor CRUD, client checklist, auto-complete trigger
6. Post-mortgage dashboard (spec `screens/36`): mortgage data display, donut chart, amortization table, drawdown timeline
7. Monthly recalculation job: CPI linkage update, variable rate anchor updates, prime track updates
8. Drawdown tracking: per-tranche entry, alerts for upcoming drawdowns
9. Background job: parameter change → recalculate all active applications atomically

**Success criteria:** Admin updates CPI → all active applications recalculate → clients see updated clock values. Post-mortgage dashboard shows correct amortization schedule.

---

### Phase 6 — Security Hardening + Launch Prep (Week 18)
**Goal:** prod-ready. Pass security audit criteria.

**Deliverables:**
1. AES-256 encryption for all PII fields at rest (Privacy Protection Law Standard 13)
2. TLS 1.3 enforced (infrastructure config)
3. Full audit log coverage verified: every state change, every admin action
4. Rate limiting on OTP endpoints, all public routes
5. Input validation and sanitization on all API boundaries (Zod schemas)
6. OWASP Top 10 review: SQL injection (Prisma parameterized), XSS (DOMPurify/CSP), CSRF, auth gaps
7. Soft-delete verification: no hard deletes anywhere in codebase
8. 7-year data retention policy enforcement
9. Load test: 100 concurrent users, calculation response < 500ms, page load < 3s on 4G
10. E2E tests for all 3 tier flows (Playwright)

**Success criteria:** Security checklist passes. Load test passes. All 3 tier flows run E2E without error.

---

## NOT in Scope (v1)

- Payment processing (tier pricing is display-only, admin assigns manually)
- E-signature (client downloads PDF, signs physically, re-uploads)
- Bank API integrations (bank responses entered manually)
- Refinancing/renewal/mortgage insurance
- WCAG 2.1 AA full compliance (v2 stub: `v2/48-v2-accessibility.md`)
- AI document validation (v2 stub: `v2/50-v2-document-ai-validation.md`)
- Refinancing alerts (v2 stub: `v2/49-v2-refinancing-alerts.md`)

## What Already Exists

| Component | Status |
|---|---|
| 50 spec files in `docs/specs/` | Complete — implementation source of truth |
| Hebrew requirements doc (`איפיון_מערכת.md`) | Complete — original requirements |
| Admin UI reference (`סימולטור_משכנתא.html`) | Complete — UI/theme reference only |
| Git repo + GitHub remote | Initialized |
| CLAUDE.md with skill routing | In place |

## Team

- Single developer (or small team)
- All implementation decisions backed by spec files; no guessing

## Risks

| Risk | Mitigation |
|---|---|
| Mortgage calculation correctness | Unit tests with verified manual examples before Phase 3 |
| RTL layout complexity | Tailwind `dir="rtl"` + early design system validation in Phase 1 |
| Israeli bank PDF formats for doc parsing | v1 defers to manual entry; v2 adds OCR |
| Gov.il eligibility table values | Spec notes these must be verified before go-live |
| OTP deliverability in Israel | Twilio IL gateway + email fallback |
| Data privacy compliance audit | Privacy Protection Law Standard 13 checklist in Phase 6 |

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|-----------|---------|
