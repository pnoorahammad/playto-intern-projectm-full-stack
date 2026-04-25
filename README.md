# Playto Pay: Payout Engine

A production-grade, concurrency-safe, idempotent payout engine built with Django, PostgreSQL, Celery, and React.

## Live Deployment
- **Frontend:** https://playto-intern-projectm-full-stack-1axo-3seswfi7j.vercel.app
- **Backend API:** https://playto-intern-projectm-full-stack-1.onrender.com

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Database | PostgreSQL (row-level locking via `SELECT FOR UPDATE`) |
| Async Workers | Celery + Redis |
| Frontend | React + Vite |
| Backend Hosting | Render |
| Frontend Hosting | Vercel |

## Core Features
1. **Append-only Ledger** — Balance derived via SQL aggregation, never stored as mutable state
2. **Concurrency Safety** — `SELECT ... FOR UPDATE` row locks eliminate double-spend race conditions
3. **Idempotency** — Per-merchant `Idempotency-Key` tracking prevents duplicate payouts
4. **Atomic Refunds** — Failed payout refunds committed in same transaction as status update
5. **State Machine** — Strict `PENDING → PROCESSING → COMPLETED/FAILED` transitions

## API Documentation

### Health Check
`GET /`
```json
{"status": "API Running", "version": "v1", "service": "Playto Payout Engine"}
```

### Get Balance
`GET /api/v1/balance/`
```json
{"balance_paise": 994000}
```

### List Payouts
`GET /api/v1/payouts/`
```json
[
  {
    "id": 1,
    "amount_paise": 6000,
    "bank_account_id": "bank_abc",
    "status": "COMPLETED",
    "idempotency_key": "uuid-key-here",
    "created_at": "2026-04-25T06:20:38Z"
  }
]
```

### Create Payout
`POST /api/v1/payouts/`

**Headers:**
```
Idempotency-Key: <unique-uuid>
Content-Type: application/json
```

**Body:**
```json
{"amount_paise": 6000, "bank_account_id": "bank_abc"}
```

**Response (201):**
```json
{"payout_id": 1, "status": "PENDING"}
```

## Local Setup

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Add `VITE_API_BASE_URL=http://localhost:8000/api/v1` to `frontend/.env.local`

## Architecture
See [EXPLAINER.md](./EXPLAINER.md) for deep-dive into ledger design, concurrency locks, idempotency, and state machine logic.
