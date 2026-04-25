# Playto Pay: Payout Engine

A robust, production-grade fintech payout engine built with Django, Django REST Framework, PostgreSQL, and Celery.

## Project Overview
This project simulates the core infrastructure of a cross-border payments payout system. It strictly enforces financial integrity by replacing mutable balance fields with a deterministic append-only ledger and implementing absolute concurrency safety using PostgreSQL row-level locks. 

## Tech Stack
* **Backend:** Django, Django REST Framework
* **Database:** PostgreSQL (Required for `SELECT FOR UPDATE` functionality)
* **Async Workers:** Celery + Redis
* **Frontend:** React (Vite)

## Core Features
1. **Idempotency:** Hardened against duplicate network requests via an `Idempotency-Key` tracking system that serializes duplicate calls safely.
2. **Concurrency Safety:** Completely eliminates Check-Then-Act (TOCTOU) double-spend vulnerabilities using DB-level `SELECT ... FOR UPDATE` row locks.
3. **Ledger Integrity:** Balances are derived dynamically via `Coalesce(Sum())` aggregations rather than a mutable integer field.
4. **Atomic Refunds:** Celery workers simulate upstream bank interactions, executing localized atomic refunds automatically upon network failure.

## API Documentation

### Create Payout
`POST /api/v1/payouts/`

**Headers:**
* `Idempotency-Key` (Required): Unique UUID string per request.
* `Authorization`: Bearer token

**Body:**
```json
{
    "amount_paise": 6000,
    "bank_account_id": "bank_123abc"
}
```

**Response (201 Created):**
```json
{
    "payout_id": 142,
    "status": "PENDING"
}
```

## Setup Instructions

### Backend (Django)
1. Clone the repository and `cd backend/`
2. Create virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Setup `.env` file with `DATABASE_URL` and `REDIS_URL`.
5. Run migrations: `python manage.py migrate`
6. Start Celery worker: `celery -A core worker -l INFO`
7. Start server: `python manage.py runserver`

### Frontend (React)
1. `cd frontend/`
2. Install dependencies: `npm install`
3. Create `.env.local` and add `VITE_API_BASE_URL=http://localhost:8000/api/v1`
4. Start dev server: `npm run dev`

## Architectural Details
Please read the attached `EXPLAINER.md` for a deep dive into the ledger architecture, concurrency locks, state machine invariants, and atomic failure handling logic.
