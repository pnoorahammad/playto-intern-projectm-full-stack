from django.urls import path
from .views import PayoutView

urlpatterns = [
    path('payouts/', PayoutView.as_view(), name='payout-create'),
]
