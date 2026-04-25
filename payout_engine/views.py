from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .services import PayoutService
from .exceptions import InsufficientFundsError
from .tasks import process_payout_task

class PayoutView(APIView):
    """
    HTTP Interface for Payout creation.
    Focuses strictly on presentation logic: Request validation, error formatting, and HTTP dispatching.
    Delegates all domain and database logic to the Services layer.
    """
    def post(self, request):
        amount_paise = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')
        idem_key_header = request.headers.get('Idempotency-Key')

        # 1. Presentation/Input Validation
        if not idem_key_header or not isinstance(amount_paise, int) or amount_paise <= 0 or not bank_account_id:
            return Response({"error": "Invalid request payload"}, status=status.HTTP_400_BAD_REQUEST)

        merchant = request.user.merchant

        # 2. Domain Logic Delegation
        try:
            payout, is_new_request, idem_obj = PayoutService.initiate_payout(
                merchant_id=merchant.id,
                amount_paise=amount_paise,
                bank_account_id=bank_account_id,
                idempotency_key=idem_key_header
            )
            
            # If the request was successfully serialized and processed before, return its cached response
            if not is_new_request:
                return Response(idem_obj.response_body, status=idem_obj.response_status)
            
            # Dispatch background task strictly upon successful DB commit
            transaction.on_commit(lambda: process_payout_task.delay(payout.id))
            
            return Response(idem_obj.response_body, status=status.HTTP_201_CREATED)

        except InsufficientFundsError as e:
            # We don't cache 400 validation errors in the idempotency table.
            # If they retry with the same key, it simply runs validation again and returns 400.
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
