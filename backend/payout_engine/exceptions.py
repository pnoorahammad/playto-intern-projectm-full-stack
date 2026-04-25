class PayoutEngineError(Exception):
    """Base exception for Payout Engine errors."""
    pass

class InsufficientFundsError(PayoutEngineError):
    """Raised when a merchant has insufficient balance for a payout."""
    pass

class IdempotencyConflictError(PayoutEngineError):
    """Raised when a concurrent request with the same idempotency key is detected."""
    pass
