from rest_framework.routers import DefaultRouter
from .views import BankUserViewSet, TransferViewSet, WithdrawalViewSet, AccountViewSet

router = DefaultRouter()
router.register(r'users', BankUserViewSet, basename='users')
router.register(r'accounts', AccountViewSet, basename='accounts')
router.register(r'transfers', TransferViewSet, basename='transfers')
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawals')

urlpatterns = router.urls