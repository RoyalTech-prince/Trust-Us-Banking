from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Home message function for the home url
def home_welcome(request):
    return JsonResponse({
        "message": "Welcome to the Royal Tech Multi-Bank Ecosystem!", 
        "status": "Operational", 
        "system_type": "Universal User Identity (PostgreSQL/Neon)",
        "documentation_url": "/api/docs/"
    })

urlpatterns = [
    # General Routes
    path('', home_welcome, name='home'),
    path('admin/', admin.site.urls),
    
    # App-specific logic (Registration, Login, Transactions)
    path('api/', include('accounts.urls')),
    
    # Documentation & Schema (Swagger UI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]