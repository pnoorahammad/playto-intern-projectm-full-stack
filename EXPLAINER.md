# Playto Pay: Payout Engine — Architecture Explainer

## 1. Ledger Design
**Why an append-only ledger instead of a `balance` field?**

A single mutable `balance` integer is a fintech anti-pattern. It creates a single point of failure and makes tracing the history of funds impossible. Mutating balance overwrites previous state — you cannot prove *how* the balance reached its current value.

By using an append-only `LedgerEntry` system (`CREDIT`/`DEBIT`), the balance becomes a **deterministic, read-only projection** of all financial events:

```python
# Balance is always derived — never stored
balance = LedgerEntry.objects.filter(merchant=merchant).aggregate(
    balance=Coalesce(
        Sum('amount_paise', filter=Q(transaction_type='CREDIT')) -
        Sum('amount_paise', filter=Q(transaction_type='DEBIT')),
        Value(0)
    )
)['balance']
```

This provides an unbreakable audit trail and eliminates an entire class of corruption bugs.

---

## 2. Concurrency Safety (`SELECT ... FOR UPDATE`)
**What DB primitive is used?**

```python
Merchant.objects.select_for_update().get(id=merchant_id)
```

This executes a PostgreSQL `SELECT ... FOR UPDATE` row-level lock.

**How it eliminates race conditions:**

When Merchant A (₹100 balance) fires two ₹60 payout requests simultaneously:
- Request 1 acquires the row lock → reads balance (₹100) → debits ₹60 → commits → releases lock
- Request 2 was blocked at the DB level → now unblocked → reads NEW balance (₹40) → rejects with InsufficientFunds

This eliminates the Check-Then-Act (TOCTOU) vulnerability completely. No Python-level balance arithmetic is ever used.

**AI Mistake Fixed:**
```python
# ❌ WRONG (race condition — both threads see balance=100)
merchant = Merchant.objects.get(id=merchant_id)
if merchant.balance >= amount:
    merchant.balance -= amount
    merchant.save()

# ✅ CORRECT (serialized via DB row lock)
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    balance = LedgerEntry.objects.get_balance(merchant)  # SQL aggregation
    if balance < amount:
        raise InsufficientFundsError()
```

---

## 3. Idempotency Handling
**How duplicate requests are prevented:**

Each request carries an `Idempotency-Key` header. We use the `IdempotencyKey` model with `get_or_create` **inside the same locked transaction**:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)  # Lock first
    idem_obj, created = IdempotencyKey.objects.get_or_create(
        merchant=merchant, key=idempotency_key
    )
    if not created:
        return cached_response  # Duplicate — return exact same response
```

**Why idempotency check is INSIDE the lock:**
If the idempotency check happened before the lock, two concurrent identical requests could both pass the check simultaneously and both create payouts — a race condition. Placing it inside the lock serializes this safely.

**In-flight handling:**
If the idempotency key exists but has no `response_status` yet (still processing), we return `409 Conflict` to prevent retry stacking.

---

## 4. State Machine & Atomic Failure Handling
**Valid state transitions:**
```
PENDING → PROCESSING → COMPLETED
PENDING → PROCESSING → FAILED
```

Invalid transitions are blocked in `finalize_payout()`:
```python
if payout.status != Payout.PayoutStatus.PROCESSING:
    return payout  # Guard against invalid transitions
```

**Atomic refund on failure:**
```python
with transaction.atomic():
    payout.status = Payout.PayoutStatus.FAILED
    payout.save()
    LedgerEntry.objects.create(  # Refund in same atomic block
        transaction_type=LedgerEntry.TransactionType.CREDIT,
        amount_paise=payout.amount_paise,
        reference_id=f"refund_failed_{payout.id}"
    )
```

Both the status update and the refund ledger entry are committed atomically. A crash mid-refund rolls back the entire block — the merchant's funds are never permanently lost.

---

## 5. Background Worker & Retry Logic
**Celery task with exponential backoff:**
```python
@shared_task(bind=True, max_retries=3, retry_backoff=True)
def process_payout_task(self, payout_id):
    # 70% success, 20% failure, 10% retry (timeout)
    outcome = BankAPIMock.transfer(payout_id, amount, account)
    ...
    except TimeoutError as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    except MaxRetriesExceededError:
        PayoutService.handle_terminal_failure(payout_id)  # Refund
```

**Downstream idempotency:**
`payout_id` is passed to the bank API as the idempotency key. If our network times out but the bank processed it, retrying with the same `payout_id` returns the original result — preventing double-crediting.
