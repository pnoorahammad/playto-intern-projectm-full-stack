from django.urls import path, include

urlpatterns = [
    # Route all v1 API traffic to the payout engine
    path('api/v1/', include('payout_engine.urls')),
]
