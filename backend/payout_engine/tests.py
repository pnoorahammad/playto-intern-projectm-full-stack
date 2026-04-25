from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status
import threading
from payout_engine.models.merchant import Merchant
from payout_engine.models.ledger_entry import LedgerEntry
from unittest.mock import patch

class PayoutConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        # Fund the merchant with 100 paise
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100,
            transaction_type=LedgerEntry.TransactionType.CREDIT,
            reference_id="initial_funding",
            description="Funding"
        )
        self.client = APIClient()
        # Mocking auth logic depending on implementation
        class MockUser:
            merchant = self.merchant
        self.client.force_authenticate(user=MockUser())

    def test_concurrent_payout_race_condition(self):
        """
        Test that two concurrent requests for 60 paise against a balance of 100 
        result in only ONE success, preventing a double-spend via SELECT FOR UPDATE.
        """
        results = []
        
        def make_request(idem_key):
            response = self.client.post('/api/v1/payouts/', {
                'amount_paise': 60,
                'bank_account_id': 'bank_123'
            }, format='json', HTTP_IDEMPOTENCY_KEY=idem_key)
            results.append(response.status_code)

        # Different idempotency keys to trigger pure balance concurrency checks
        with patch('payout_engine.views.process_payout_task.delay'):
            t1 = threading.Thread(target=make_request, args=('key1',))
            t2 = threading.Thread(target=make_request, args=('key2',))

            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # One request must succeed (201), the other must fail on balance validation (400)
        self.assertIn(status.HTTP_201_CREATED, results)
        self.assertIn(status.HTTP_400_BAD_REQUEST, results)

        # Balance should be strictly 40
        balance = LedgerEntry.objects.get_balance(self.merchant)
        self.assertEqual(balance, 40)

class PayoutIdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=1000,
            transaction_type=LedgerEntry.TransactionType.CREDIT,
            reference_id="initial_funding",
            description="Funding"
        )
        self.client = APIClient()
        class MockUser:
            merchant = self.merchant
        self.client.force_authenticate(user=MockUser())

    @patch('payout_engine.views.process_payout_task.delay')
    def test_idempotency_exact_duplicate(self, mock_delay):
        """
        Test that submitting the same request twice returns the exact same cached response.
        """
        payload = {'amount_paise': 100, 'bank_account_id': 'bank_123'}
        
        # First request
        res1 = self.client.post('/api/v1/payouts/', payload, format='json', HTTP_IDEMPOTENCY_KEY='idem_test_999')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Duplicate request
        res2 = self.client.post('/api/v1/payouts/', payload, format='json', HTTP_IDEMPOTENCY_KEY='idem_test_999')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        
        # Response body should be identical
        self.assertEqual(res1.data, res2.data)

        # Ensure only ONE hold ledger entry was created
        debits = LedgerEntry.objects.filter(transaction_type=LedgerEntry.TransactionType.DEBIT).count()
        self.assertEqual(debits, 1)
