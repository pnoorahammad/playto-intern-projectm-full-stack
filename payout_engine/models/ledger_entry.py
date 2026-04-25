from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from .merchant import Merchant

class LedgerEntryQuerySet(models.QuerySet):
    def get_balance(self, merchant) -> int:
        """Deterministically calculate available balance using append-only DB records."""
        credits = self.filter(
            merchant=merchant, 
            transaction_type=LedgerEntry.TransactionType.CREDIT
        ).aggregate(total=Coalesce(Sum('amount_paise'), 0))['total']
        
        debits = self.filter(
            merchant=merchant, 
            transaction_type=LedgerEntry.TransactionType.DEBIT
        ).aggregate(total=Coalesce(Sum('amount_paise'), 0))['total']
        
        return credits - debits

class LedgerEntry(models.Model):
    class TransactionType(models.TextChoices):
        CREDIT = 'CREDIT'
        DEBIT = 'DEBIT'

    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='ledger_entries')
    amount_paise = models.PositiveBigIntegerField()
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    reference_id = models.CharField(max_length=255, help_text="ID of the related Payout or Payment")
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = LedgerEntryQuerySet.as_manager()

    class Meta:
        db_table = 'ledger_entry'
