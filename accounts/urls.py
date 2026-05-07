from django.urls import path
from .views import (
    MultiBankLoginView,
    UniversalRegistrationView,
    BankEnrollmentView,
    TransferCreateView,
    WithdrawalCreateView,
    AccountDetailView,
    UserAccountsListView,
    BankUserListView,
    BankUserDetailView
)

urlpatterns = [
    # --- Universal User CRUD ---
    path('users/', BankUserListView.as_view(), name='user_list'), # List all
    path('users/<str:matricule>/', BankUserDetailView.as_view(), name='user_detail'), # Read, Update, Delete
    # --- Authentication & Identity ---
    path('auth/login/', MultiBankLoginView.as_view(), name='login'),
    path('auth/register-universal/', UniversalRegistrationView.as_view(), name='register_universal'),
    path('auth/enroll-bank/', BankEnrollmentView.as_view(), name='enroll_bank'),

    # --- Transactions ---
    path('transactions/transfer/', TransferCreateView.as_view(), name='transfer_create'),
    path('transactions/withdraw/', WithdrawalCreateView.as_view(), name='withdraw_create'),

    # --- Information & Discovery ---
    path('accounts/<uuid:account_id>/', AccountDetailView.as_view(), name='account_detail'),
    path('accounts/user/<str:matricule>/', UserAccountsListView.as_view(), name='user_accounts_list'),
]