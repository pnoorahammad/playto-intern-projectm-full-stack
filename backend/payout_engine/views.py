from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .services import PayoutService
from .exceptions import InsufficientFundsError
from .tasks import process_payout_task
from .models.merchant import Merchant
from .models.ledger_entry import LedgerEntry
from .models.payout import Payout

def _get_merchant():
    merchant = Merchant.objects.first()
    if not merchant:
        merchant = Merchant.objects.create(name="Playto Demo Merchant")
        # Initialize with 10,000 INR = 1,000,000 paise
        LedgerEntry.objects.create(
            merchant=merchant, 
            amount_paise=1000000, 
            transaction_type=LedgerEntry.TransactionType.CREDIT, 
            description="Initial Funding"
        )
    return merchant

class PayoutView(APIView):
    def get(self, request):
        merchant = _get_merchant()
        payouts = Payout.objects.filter(merchant=merchant).order_by('-created_at')
        data = [
            {
                "id": p.id,
                "amount_paise": p.amount_paise,
                "bank_account_id": p.bank_account_id,
                "status": p.status,
                "idempotency_key": p.idempotency_key,
                "created_at": p.created_at
            } for p in payouts
        ]
        return Response(data)

    def post(self, request):
        try:
            amount_paise = int(request.data.get('amount_paise', 0))
        except (ValueError, TypeError):
            amount_paise = 0
            
        bank_account_id = request.data.get('bank_account_id')
        # Support sending idempotency key in headers or body for easy frontend test
        idem_key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')

        if not idem_key or amount_paise <= 0 or not bank_account_id:
            return Response({"error": "Invalid request payload"}, status=status.HTTP_400_BAD_REQUEST)

        merchant = _get_merchant()

        try:
            payout, is_new_request, idem_obj = PayoutService.initiate_payout(
                merchant_id=merchant.id,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                idempotency_key=idem_key
            )
            
            if not is_new_request:
                return Response(idem_obj.response_body, status=idem_obj.response_status)
            
            transaction.on_commit(lambda: process_payout_task.delay(payout.id))
            return Response(idem_obj.response_body, status=status.HTTP_201_CREATED)

        except InsufficientFundsError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class BalanceView(APIView):
    def get(self, request):
        merchant = _get_merchant()
        balance = LedgerEntry.objects.get_balance(merchant)
        return Response({"balance_paise": balance})
