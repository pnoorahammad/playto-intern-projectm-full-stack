import random
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from .services import PayoutService

class BankAPIMock:
    """Mock implementation of the external bank network API."""
    @staticmethod
    def transfer(payout_id: int, amount: int, account: str) -> str:
        """
        CRITICAL FINTECH FIX:
        The bank API *must* accept our payout_id (or a derived idempotency key) 
        to ensure downstream idempotency. If our network times out but the bank 
        actually processed the transfer, our celery retry will send the same payout_id. 
        The bank must recognize it and return the original success rather than double-crediting.
        """
        outcome = random.choices(['SUCCESS', 'FAILURE', 'STUCK'], weights=[0.7, 0.2, 0.1])[0]
        if outcome == 'STUCK':
            raise TimeoutError("Bank API timeout")
        return outcome

@shared_task(bind=True, max_retries=3, retry_backoff=True)
def process_payout_task(self, payout_id: int):
    """
    Background worker task. 
    Focuses purely on orchestrating background execution, interacting with external network dependencies,
    and managing retry lifecycles. Delegates all database state transitions to the Service layer.
    """
    
    # 1. State lock and transition
    payout = PayoutService.process_payout_transition(payout_id)
    if payout.status != 'PROCESSING':
        return

    # 2. External API interaction (Outside of DB transaction locks)
    try:
        # Pass the payout_id to prevent double-spending downstream on network retries
        outcome = BankAPIMock.transfer(payout.id, payout.amount_paise, payout.bank_account_id)
        
        # 3. Finalize
        PayoutService.finalize_payout(payout_id, outcome)

    except TimeoutError as e:
        try:
            # Trigger celery retry explicitly
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            # 4. Terminal Failure Recovery
            PayoutService.handle_terminal_failure(payout_id)
