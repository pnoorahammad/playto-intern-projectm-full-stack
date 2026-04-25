# Playto Pay: Payout Engine Design

## 1. Ledger Design
**Why ledger instead of storing balance?**
A single integer `balance` field on a `Merchant` model is a notorious anti-pattern in fintech. It creates a single point of failure and makes tracing the history of funds impossible. Mutating a balance overwrites the previous state, meaning you cannot definitively prove *how* the balance reached its current state. By using an append-only `LedgerEntry` system (`CREDIT` and `DEBIT`), the balance becomes a deterministic, read-only projection of all financial events. You get an unbreakable audit trail out of the box.

## 2. Concurrency
**What exact DB primitive is used?**
We use `Merchant.objects.select_for_update().get(id=merchant_id)`, which executes a PostgreSQL `SELECT ... FOR UPDATE` row-level lock.

**Why it prevents race conditions?**
When Merchant A with ₹100 requests two ₹60 payouts simultaneously, Request 1 locks the merchant row. Request 2 attempts to lock the exact same row but is blocked by the DB engine and placed in a wait queue. Request 1 calculates the balance (₹100), authorizes the ₹60 debit, and commits the transaction. The lock is then released. Request 2 is unblocked, reads the new balance (₹40), and safely rejects the transaction due to insufficient funds. It completely eliminates the Check-Then-Act (TOCTOU) vulnerability.

## 3. Idempotency
**How duplicate requests are handled?**
Each request includes an `Idempotency-Key` header. We use the `IdempotencyKey` model to track requests per merchant. When a request enters, we attempt a `get_or_create`. If `created` is False, we know it's a duplicate. We then return the exact HTTP status and body stored in the `IdempotencyKey` record.

**What happens if request is in-flight?**
If a duplicate request arrives while the first is still processing, the `IdempotencyKey` row exists, but its `response_status` is `null`. In this case, we immediately return a `409 Conflict`. This explicitly blocks aggressive retries from stacking up and consuming database connections or causing race conditions during the initial processing window.

## 4. Failure Handling
**How refund is atomic?**
In the background Celery worker, if the simulated bank API fails, we open a `transaction.atomic()` block. Inside this single block, we update the payout status to `FAILED` and insert a `CREDIT` `LedgerEntry` for the exact amount. Because these two operations are wrapped in an atomic transaction, they are committed to the disk simultaneously. If the database crashes mid-refund, the entire transaction rolls back, leaving the payout in `PROCESSING`. The system will never end up in a corrupted state where a payout is marked failed but the merchant's funds are permanently lost.

## 5. AI Audit
**AI Mistake Example:**
A common mistake an AI makes is calculating the balance inside the application code without taking a database lock, like so:
```python
# BAD CODE
merchant = Merchant.objects.get(id=merchant_id)
if merchant.balance >= amount:
    merchant.balance -= amount
    merchant.save()
```
**Why it is wrong and my fix:**
This introduces a severe race condition. If two requests execute this block concurrently, both query the DB and see `balance = 1000`. Both deduct `600`, and both save `400` back to the database. The merchant successfully spent `1200` from a `1000` balance. My fix strictly avoids this by eliminating the `balance` field completely, using a `LedgerEntry` table, and using `SELECT ... FOR UPDATE` to serialize the transactions at the database engine level.
