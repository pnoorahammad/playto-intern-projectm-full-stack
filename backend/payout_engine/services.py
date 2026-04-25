from django.db import transaction
from typing import Tuple, Optional
from .models import Merchant, LedgerEntry, Payout, IdempotencyKey
from .exceptions import InsufficientFundsError

class PayoutService:
    @staticmethod
    def initiate_payout(merchant_id: int, amount_paise: int, bank_account_id: str, idempotency_key: str) -> Tuple[Optional[Payout], bool, Optional[IdempotencyKey]]:
        """
        Executes strictly atomic domain logic to authorize and hold funds.
        Returns: (Payout object, created boolean, IdempotencyKey object)
        """
        if amount_paise <= 0:
            raise ValueError("Payout amount must be strictly positive.")

        with transaction.atomic():
            # 1. STRICT LOCKING: Serialize all operations for this merchant.
            # This completely eliminates both balance race conditions AND idempotency race conditions.
            locked_merchant = Merchant.objects.get_for_update(merchant_id)

            # 2. IDEMPOTENCY CHECK (Protected by the Merchant lock)
            # If two identical requests hit exactly at the same time, the second one waits 
            # for the lock, then safely reads the response committed by the first one.
            idem_obj, created = IdempotencyKey.objects.get_or_create(
                merchant=locked_merchant, 
                key=idempotency_key
            )
            
            if not created:
                # Duplicate request detected. Return the cached state.
                return None, False, idem_obj

            # 3. BALANCE CHECK
            current_balance = LedgerEntry.objects.get_balance(locked_merchant)
            if current_balance < amount_paise:
                # Transaction rolls back automatically, deleting the IdempotencyKey.
                # A future retry will re-evaluate the balance, which is the correct behavior.
                raise InsufficientFundsError("Insufficient funds for payout")

            # 4. CREATE PAYOUT
            payout = Payout.objects.create(
                merchant=locked_merchant,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                status=Payout.PayoutStatus.PENDING,
                idempotency_key=idempotency_key
            )

            # 5. HOLD FUNDS
            LedgerEntry.objects.create(
                merchant=locked_merchant,
                amount_paise=amount_paise,
                transaction_type=LedgerEntry.TransactionType.DEBIT,
                reference_id=f"payout_{payout.id}",
                description=f"Fund hold for payout {payout.id}"
            )
            
            # 6. CACHE SUCCESS RESPONSE IN IDEMPOTENCY RECORD
            response_body = {"payout_id": payout.id, "status": payout.status}
            idem_obj.response_status = 201
            idem_obj.response_body = response_body
            idem_obj.save(update_fields=['response_status', 'response_body'])

            return payout, True, idem_obj

    @staticmethod
    def process_payout_transition(payout_id: int) -> Payout:
        """Idempotent state transition to PROCESSING mode."""
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status in [Payout.PayoutStatus.PENDING, Payout.PayoutStatus.PROCESSING]:
                payout.status = Payout.PayoutStatus.PROCESSING
                payout.save(update_fields=['status', 'updated_at'])
            return payout

    @staticmethod
    def finalize_payout(payout_id: int, outcome: str) -> Payout:
        """Finalizes the payout transaction and handles refunds on failures."""
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status != Payout.PayoutStatus.PROCESSING:
                return payout

            if outcome == 'SUCCESS':
                payout.status = Payout.PayoutStatus.COMPLETED
                
            elif outcome == 'FAILURE':
                payout.status = Payout.PayoutStatus.FAILED
                
                # ATOMIC REFUND: Restore the balance
                LedgerEntry.objects.create(
                    merchant=payout.merchant,
                    amount_paise=payout.amount_paise,
                    transaction_type=LedgerEntry.TransactionType.CREDIT,
                    reference_id=f"refund_failed_{payout.id}",
                    description="Refund for failed payout"
                )
                
            payout.save(update_fields=['status', 'updated_at'])
            return payout

    @staticmethod
    def handle_terminal_failure(payout_id: int) -> None:
        """Handles edge-case recovery when network retries are fully exhausted."""
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status not in [Payout.PayoutStatus.FAILED, Payout.PayoutStatus.COMPLETED]:
                payout.status = Payout.PayoutStatus.FAILED
                payout.save(update_fields=['status', 'updated_at'])
                
                LedgerEntry.objects.create(
                    merchant=payout.merchant,
                    amount_paise=payout.amount_paise,
                    transaction_type=LedgerEntry.TransactionType.CREDIT,
                    reference_id=f"refund_maxretries_{payout.id}",
                    description="Refund after network retries exhausted"
                )
