from rest_framework.routers import DefaultRouter
from .views import BankUserViewSet

router = DefaultRouter()
router.register(r'users', BankUserViewSet, basename='users')

urlpatterns = router.urls