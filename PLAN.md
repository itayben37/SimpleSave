<!-- /autoplan restore point: /Users/giladshekalim/.gstack/projects/GiladShekalim-SimpleSave/main-autoplan-restore-20260625-215941.md -->
# SimpleSave — Implementation Plan

## Problem Statement

Mortgage advisors in Israel manage their clients through a fragmented mix of WhatsApp messages, Google Sheets, and email. Clients have no visibility into their process and advisors have no tooling to scale beyond 10 clients. SimpleSave replaces this with a structured B2B2C platform: clients self-serve through a guided mortgage wizard, advisors manage their caseload in one dashboard, and the admin controls pricing, mixes, and rate parameters.

## What We Are Building

A full-stack Hebrew-language (RTL) web application with:
- 3 roles: Admin, Advisor, Client
- 3 service tiers: Tier 1 (self-service), Tier 2 (async advisor), Tier 3 (dedicated advisor + calendar)
- OTP-only auth via Firebase Auth (phone or email), no passwords
- 15-state application lifecycle (questionnaire → active mortgage)
- Mortgage mix calculator with 5 "clocks" (Chart.js), Spitzer and Keren Shava amortization
- Server-side PDF generation (authorization letters via WeasyPrint + Jinja2)
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
| Frontend | React 18 (Vite, JavaScript — no TypeScript) | Component model for wizard/tabs/RTL; Vite gives fast dev cycle; no SSR needed (app is auth-gated) |
| Styling | Tailwind CSS (via npm) | Utility-first, RTL via `dir="rtl"` + logical properties, dark admin theme with CSS vars |
| State | React Context + hooks | No external state lib; Context per domain (auth, app, wizard) |
| Charts | Chart.js + react-chartjs-2 | Confirmed from spec; 5-clock drill-down, donut, amortization |
| Backend | Python 3.12 + FastAPI | Financial calculation engine benefits from Python decimal precision; async-native; auto OpenAPI docs |
| ORM | SQLAlchemy 2.0 (async) + Alembic migrations | Mature, type-safe, async-capable; Alembic handles versioned schema migrations |
| Database | Cloud SQL (PostgreSQL 15) via GCP | Relational integrity for 18 spec-defined entities; JSONB for flexible fields; FK constraints preserved |
| File storage | Firebase Storage | Integrates natively with Firebase Auth security rules; replaces S3 |
| Auth | Firebase Auth (phone OTP + email OTP) | Handles OTP send/verify, rate limiting, lockout, session tokens natively; backend verifies via firebase-admin Python SDK |
| PDF | WeasyPrint + Jinja2 | Python-native HTML→PDF; Jinja2 templates replace Handlebars; no headless browser overhead |
| Email | SendGrid (called from FastAPI) | 15 email templates; pluggable interface per spec `07-email-engine.md` |
| Calendar | Custom availability slots (v1) | Tier 3 booking only; no external dependency |
| Deployment — Frontend | Firebase Hosting | Serves built React SPA (static bundle); global CDN |
| Deployment — Backend | Cloud Run (containerized FastAPI) | Serverless containers; auto-scales; connects to Cloud SQL via private IP |
| Deployment — DB | Cloud SQL (PostgreSQL) | Managed, automated backups, private VPC peering to Cloud Run |

## Repository Structure

```
SimpleSave/
├── docs/
│   └── specs/                  ← all 50 spec MD files (source of truth)
├── frontend/                   ← Vite + React app
│   ├── src/
│   │   ├── components/         ← shared UI (Button, Modal, FileUpload, ClockCard, etc.)
│   │   ├── pages/              ← route-level components (Home, Wizard, PersonalArea, Admin, etc.)
│   │   ├── hooks/              ← custom hooks (useAuth, useApplication, useCalculation)
│   │   ├── context/            ← React Context providers (AuthContext, AppContext)
│   │   └── utils/              ← formatting, validation, RTL helpers
│   ├── public/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── backend/                    ← Python + FastAPI
│   ├── app/
│   │   ├── modules/
│   │   │   ├── auth/           ← Firebase token verification, session middleware
│   │   │   ├── applications/   ← application CRUD, state machine transitions
│   │   │   ├── documents/      ← document list generation, upload handling, review flow
│   │   │   ├── calculations/   ← Spitzer/Keren Shava engine, clocks orchestration
│   │   │   ├── notifications/  ← email dispatch, notification triggers
│   │   │   ├── admin/          ← parameter management, mix manager, rate tables
│   │   │   └── advisors/       ← advisor dashboard, task management, messaging
│   │   ├── common/             ← middleware, error handlers, audit log, DB session
│   │   ├── config/             ← env config, Firebase Admin init, regulatory param loader
│   │   ├── pdf/                ← Jinja2 templates + WeasyPrint generator
│   │   └── main.py             ← FastAPI app entry point, router registration
│   ├── migrations/             ← Alembic versioned migrations
│   ├── seeds/                  ← banks, cities, document types, SystemParameters, interest rates
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── tests/
│   ├── unit/                   ← calculation engine, state machine, eligibility
│   ├── integration/            ← API endpoints against test DB
│   └── e2e/                    ← full tier flows (Playwright)
└── infrastructure/             ← GCP + Firebase config
    ├── firebase.json            ← Hosting + Storage rules
    ├── .firebaserc
    ├── firestore.rules          ← n/a (using Cloud SQL, not Firestore)
    └── cloud-run/              ← Dockerfile, cloudbuild.yaml, service.yaml
```

## Firebase Auth Integration Notes

Firebase Auth replaces the full custom OTP implementation from spec `03-authentication.md`. The mapping:

| Spec requirement | Firebase Auth equivalent |
|---|---|
| OTP send (phone) | `signInWithPhoneNumber()` — Firebase handles SMS via Twilio/GCP |
| OTP send (email) | `sendSignInLinkToEmail()` — email magic link |
| OTP verify + session token | Firebase SDK completes verification, issues ID token |
| Session sliding window (24h) | Firebase ID tokens expire in 1h; `getIdToken(true)` refreshes silently |
| 5-attempt lockout | Firebase Auth built-in abuse prevention; Admin SDK can disable user |
| Admin unlock account | `admin.auth().updateUser(uid, { disabled: false })` |
| Role assignment | Firebase Auth custom claims: `{ role: 'admin' | 'advisor' | 'client' }` — set via Admin SDK on account creation |
| Backend verification | FastAPI middleware calls `firebase_admin.auth.verify_id_token(token)` on every request |
| New user detection | `is_new_user` flag in Firebase `UserRecord`; triggers DB row creation |
| Admin/Advisor provisioning | Admin calls `/admin/users` endpoint → FastAPI creates Firebase Auth user + sets custom claim + inserts DB row |

**Key difference from spec:** The `OTPSession`, `sessions`, and `otp_lockouts` DB tables are not needed. Firebase owns that state. The `AuditLog` still records all auth events (backend logs on token verify).

## Build Phases

> **Rule:** Every phase listed here must be reviewed and approved before implementation begins. No phase starts without sign-off.

---

### Phase 1 — Foundation (Weeks 1–3)
**Goal:** Working repo, DB schema, Firebase Auth, skeleton FastAPI routes. No frontend yet.

**Deliverables:**
1. Repository scaffolding: `frontend/`, `backend/`, `tests/`, `infrastructure/` as per structure above
2. Cloud SQL (PostgreSQL) schema via Alembic migrations — all 18 entities from spec `02-data-model.md`
   - Drop `OTPSession` / `sessions` / `otp_lockouts` (Firebase Auth owns these)
   - All other entities unchanged; JSONB fields preserved
3. Seed data: banks, cities, document types, default SystemParameters, InterestRateTable initial values
4. Firebase project setup: Auth (phone + email providers enabled), Storage bucket, Hosting target
5. FastAPI app skeleton: router registration, CORS, error handler, health endpoint
6. Firebase Auth middleware: `verify_firebase_token` dependency; extracts `uid`, `role` custom claim
7. Role guard: `require_role('admin')` / `require_role('advisor')` / `require_role('client')` FastAPI dependencies
8. Audit log middleware: writes `AuditLog` DB row on every state-changing POST/PATCH/DELETE
9. Admin SDK endpoint: `POST /admin/users` — creates Firebase Auth user + sets role custom claim + inserts User DB row
10. Vite + React project init: RTL config (`dir="rtl"`), Hebrew font (Heebo via Google Fonts), Tailwind CSS, CSS variables matching admin reference UI (`--bg:#0f1623`, `--accent:#3b82f6`)
11. Firebase Hosting config: `firebase.json` points to `frontend/dist`; rewrites all routes to `index.html` (SPA)

**Success criteria:** `GET /health` returns 200. DB migrations run clean. Posting a Firebase ID token to a protected route returns 403 for wrong role, 200 for correct role. `npm run build` in `frontend/` produces a deployable bundle.

---

### Phase 2 — Questionnaire + Clocks (Weeks 4–6)
**Goal:** Full guest + client experience up to tier selection, including mortgage calculator.

**Deliverables:**
1. React Router setup: public routes (Home, Wizard, Clocks, Registration, Tier Selection) + protected routes (Personal Area)
2. 10-question mortgage wizard (spec `screens/27`, `flows/17`):
   - React multi-step form; each step is a component
   - Conditional logic between questions (e.g., Q3 answer gates Q4 options)
   - Auto-save to `sessionStorage` (pre-auth)
   - Post-Q10: Firebase Auth phone/email OTP gate (Firebase UI or custom flow using Firebase SDK)
   - On OTP success: migrate sessionStorage data → `POST /applications` to create DB record
3. Mortgage calculation engine (spec `09-mortgage-calculation-engine.md`) — Python:
   - `calculations/engine.py`: Spitzer and Keren Shava implementations using Python `Decimal`
   - CPI linkage (annual balance inflation), prime track, variable rate resets
   - All rounding rules from spec
   - Unit tests: worked example ₪1M / 25y / 3.5% = ₪5,005.84/month
4. Clocks/mix generation (spec `10-clocks-mix-generation.md`):
   - `POST /calculations/clocks` — takes application context, returns 5 clock results
   - `clock_results` cache table; recalculate on SystemParameter change
   - Risk speedometer score formula
5. Clocks screen (spec `screens/28`): React — 5 clock cards, Chart.js drill-down (monthly/cumulative toggle), risk needle chart
6. Eligibility calculator (spec `11-eligibility-calculator.md`): vatikei haaretz scoring — Python service + React widget
7. Firebase Auth flow (React): phone OTP UI with 6-digit input; on success stores Firebase ID token in memory / httpOnly cookie; `AuthContext` provides `currentUser`
8. Tier selection screen (spec `screens/46`): display-only, no payment
9. `GET /applications/wizard-state` — returns partial application for sessionStorage hydration on page reload

**Success criteria:** Guest completes wizard, registers via Firebase Auth, sees 5 clocks with correct amortization values. Calculation matches manual formula verification. Firebase ID token accepted by backend.

---

### Phase 3 — Personal Area: Client Flow (Weeks 7–10)
**Goal:** Full client lifecycle from `TIER_SELECTED` → `DOCUMENTS_SUBMITTED`.

**Deliverables:**
1. Application state machine (Python `applications/state_machine.py`): unidirectional transitions only via service layer; all transitions write AuditLog
2. Personal Area Hub (spec `screens/30`): React — 7-tab shell, lock state matrix per tier × lifecycle state
3. Personal Details (spec `screens/31`): all 18+ borrower fields, multi-borrower sub-tabs (React tabs), auto-save via debounced `PATCH /borrowers/{id}`, eligibility widget
4. Mortgage Details (spec `screens/32`): financing ratio live validation, equity sources, payment cap logic
5. Document management (spec `05-document-management.md`, `screens/33`):
   - Dynamic doc list generation per borrower profile (`GET /applications/{id}/documents`)
   - Firebase Storage upload: client uploads directly to Storage, backend records metadata via `POST /documents/{id}/upload`
   - Firebase Storage security rules: only authenticated user who owns the application can write; only their advisor and admin can read
   - React document list with status badges, rejection reason display, re-upload flow
   - PDF.js viewer modal for uploaded documents
   - Progress gate bar
6. PDF generation (spec `06-pdf-generation.md`):
   - FastAPI endpoint: `POST /applications/{id}/authorization-letters`
   - Jinja2 templates per bank (Hebrew RTL)
   - WeasyPrint renders HTML template → PDF bytes → uploaded to Firebase Storage → signed URL returned
   - Batch download: zip of all bank letters
7. Email engine (spec `07-email-engine.md`): 15 Jinja2 email templates; `notifications/email_sender.py` wraps SendGrid; pluggable interface
8. Notification triggers for all 15 events (spec `04-notification-system.md`): fired from state machine transitions and document review actions

**Success criteria:** Client fills personal details, uploads all required docs, downloads signed authorization letters. State advances to `DOCUMENTS_SUBMITTED`. All notifications fire.

---

### Phase 4 — Advisor Area + Principal Approval (Weeks 11–14)
**Goal:** Advisor manages clients, approves docs, enters bank responses.

**Deliverables:**
1. Advisor dashboard (spec `screens/44`): React — My Clients tab sorted by next action + unread messages; Tasks tab
2. Advisor client detail (spec `screens/45`): 6-tab mirror of client Personal Area with edit rights; approve/reject documents via `PATCH /documents/{id}/review`
3. Document review flow: per-document approve/reject with rejection reason; re-upload loop resets status to `uploaded`
4. Admin client management (spec `screens/42`): leads table, assign advisor modal → `POST /admin/applications/{id}/assign`
5. Admin advisors management (spec `screens/43`): add advisor (calls `POST /admin/users` with role=advisor); deactivate; bulk reassign
6. Principal approval entry: `POST /applications/{id}/principal-approvals` per bank; best-offer computation
7. Principal approval screen (spec `screens/34`): React — bank card grid, best offer badge, 2-step bank selection
8. Advisor messages / two-way chat (spec `screens/37`): React — message threads scoped to application; stage tags; read receipts via `PATCH /messages/{id}/read`
9. Tier 3 calendar booking (spec `screens/47`): React — weekly slot grid; `POST /bookings`, cancel, reschedule; 24h + 1h reminders via scheduled task in FastAPI (APScheduler)

**Success criteria:** Advisor assigns leads, approves docs, enters bank approvals. Client selects bank. State reaches `BANK_SELECTED`.

---

### Phase 5 — Admin Dashboard + Post-Mortgage (Weeks 15–17)
**Goal:** Admin controls all parameters; client tracks active mortgage.

**Deliverables:**
1. Admin overview dashboard (spec `screens/38`): React — summary cards, audit feed, unassigned queue
2. Admin mix manager (spec `screens/39`): inline track editing; 100% validation; `POST /admin/mixes/{id}/recalculate-all`
3. Admin interest rates (spec `screens/40`): dual housing/all-purpose tables; `PUT /admin/interest-rates`
4. Admin parameters (spec `screens/41`): CPI, prime, anchors; change log; `PUT /admin/parameters/{key}` triggers background recalculation
5. Collaterals screen (spec `screens/35`): React — advisor CRUD, client checklist; auto-complete trigger
6. Post-mortgage dashboard (spec `screens/36`): React — mortgage data, Chart.js donut, amortization table (react-table), drawdown timeline
7. Monthly recalculation background job: APScheduler task — CPI linkage update, variable rate anchor updates, prime track updates
8. Drawdown tracking: `POST /applications/{id}/drawdowns`; alerts for upcoming drawdowns (APScheduler)
9. Parameter change cascade: `PUT /admin/parameters/{key}` → async task recalculates all active applications → updates `clock_results` cache → pushes notification

**Success criteria:** Admin updates CPI → all active applications recalculate → clients see updated clock values. Post-mortgage dashboard shows correct amortization schedule.

---

### Phase 6 — Security Hardening + Launch Prep (Week 18)
**Goal:** Production-ready. Pass security audit criteria.

**Deliverables:**
1. AES-256 encryption for all PII fields at rest — SQLAlchemy `TypeDecorator` wraps encrypted columns (Privacy Protection Law Standard 13)
2. TLS 1.3 enforced: Cloud Run serves HTTPS only; Firebase Hosting enforces HTTPS; Cloud SQL uses SSL
3. Full audit log coverage verified: every state change, every admin action
4. Rate limiting on all public FastAPI routes: `slowapi` middleware
5. Input validation: Pydantic schemas on all request bodies (FastAPI native)
6. Firebase Storage security rules audit: no unauthenticated reads; scoped per application ownership
7. OWASP Top 10 review: SQL injection (SQLAlchemy parameterized), XSS (React escapes by default + CSP header), CSRF (Firebase ID token = stateless, not cookie-based), auth gaps
8. Soft-delete verification: no hard deletes anywhere in codebase; all deletes set `is_active = false` or `deleted_at`
9. 7-year data retention policy enforcement
10. Load test: 100 concurrent users, calculation response < 500ms, page load < 3s on 4G
11. E2E tests for all 3 tier flows (Playwright against Firebase Hosting + Cloud Run staging env)

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
- **Every phase requires approval before implementation starts**

## Risks

| Risk | Mitigation |
|---|---|
| Mortgage calculation correctness | Python `Decimal` precision; unit tests with verified manual examples before Phase 3 |
| RTL layout complexity | Tailwind `dir="rtl"` + CSS logical properties; validate in Phase 1 design system |
| Firebase Auth custom claims latency | Claims propagate within seconds; token refresh on role assignment |
| Cloud SQL connection from Cloud Run | Private IP VPC peering; Cloud SQL Auth Proxy sidecar in Cloud Run |
| Israeli bank PDF formats | v1 defers to manual entry; v2 adds OCR |
| Gov.il eligibility table values | Spec notes these must be verified before go-live |
| WeasyPrint Hebrew RTL rendering | Test with real Hebrew content in Phase 3; fallback to ReportLab if needed |
| Data privacy compliance audit | Privacy Protection Law Standard 13 checklist in Phase 6 |

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|-----------|---------|
| 1 | 1 | Database: Cloud SQL (PostgreSQL) | Architecture | Open/Closed | 18-entity relational schema in spec maps 1:1; JSONB fields preserved; FK integrity maintained | Firestore (NoSQL — incompatible with relational spec without full redesign) |
| 2 | 1 | Auth: Firebase Auth (phone OTP + email OTP) | Architecture | Dependency Inversion | Replaces full custom OTP implementation; Firebase owns rate limiting, lockout, session tokens; backend verifies via Admin SDK | Custom OTP in FastAPI (higher complexity, more surface area, no benefit over Firebase) |
| 3 | 1 | Frontend: React 18 + Vite (JavaScript) | Architecture | Single Responsibility | Component model fits wizard/tabs/RTL complexity; Vite fast dev cycle; no SSR needed (auth-gated app); no TypeScript per team preference | Next.js (SSR overhead unnecessary); plain HTML/JS (insufficient structure for 7-tab SPA) |
| 4 | 1 | Backend: Python 3.12 + FastAPI | Architecture | Single Responsibility | Financial calculations benefit from Python `Decimal`; FastAPI async-native; auto OpenAPI docs match spec contracts | Node.js + Express (replaced; Python preferred) |
| 5 | 1 | ORM: SQLAlchemy 2.0 + Alembic | Architecture | Dependency Inversion | Mature async ORM; Alembic migrations = Prisma equivalent for Python | Tortoise ORM (less mature); raw asyncpg (no migration tooling) |
| 6 | 3 | File storage: Firebase Storage | Architecture | Dependency Inversion | Native Firebase Auth security rules; simpler than S3 for this Firebase-first stack | AWS S3 (requires separate IAM, no Firebase Auth integration) |
| 7 | 3 | PDF generation: WeasyPrint + Jinja2 | Architecture | Single Responsibility | Python-native HTML→PDF; no headless browser; Jinja2 = Handlebars equivalent | Puppeteer (Node.js only); ReportLab (programmatic, harder to template Hebrew RTL) |
| 8 | 1 | Deployment: Firebase Hosting + Cloud Run + Cloud SQL | Infrastructure | — | Firebase Hosting for React SPA; Cloud Run for containerized FastAPI (serverless, auto-scales); Cloud SQL private-IP to Cloud Run | AWS (Firebase-first decision made) |
