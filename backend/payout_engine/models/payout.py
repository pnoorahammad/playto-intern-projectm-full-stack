from django.db import models
from .merchant import Merchant

class Payout(models.Model):
    class PayoutStatus(models.TextChoices):
        PENDING = 'PENDING'
        PROCESSING = 'PROCESSING'
        COMPLETED = 'COMPLETED'
        FAILED = 'FAILED'

    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT)
    amount_paise = models.PositiveBigIntegerField()
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=15, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    idempotency_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payout'
        app_label = 'payout_engine'
