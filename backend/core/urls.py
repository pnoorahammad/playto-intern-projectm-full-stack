from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "API Running", "version": "v1", "service": "Playto Payout Engine"})

urlpatterns = [
    path('', health_check, name='health'),
    path('api/v1/', include('payout_engine.urls')),
]
