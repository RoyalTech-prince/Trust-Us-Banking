from django.urls import path
from .views import (
    LocalAccountBalanceView,
    MultiBankLoginView,
    TraceTransactionHistoryView,
    TransactionHistoryView,
    UniversalRegistrationView,
    BankEnrollmentView,
    BankUserListView,
    BankUserDetailView,
    AdminUnblockUserView,  # Added for Feature 6 administrative override
    TransferCreateView,
    WithdrawalCreateView,
    DepositCreateView,     # 👈 Ajout du controlleur pour les dépôts MoMo
    AccountDetailView,
    UserAccountsListView
)

urlpatterns = [
    # --- Universal User CRUD (Module 1 - Member 1) ---
    path('users/', BankUserListView.as_view(), name='user_list'),  # List all profiles
    path('users/<str:matricule>/', BankUserDetailView.as_view(), name='user_detail'),  # Read, Update, Delete by Matricule

    # --- Authentication & Identity (Module 1 & 3 - Members 1 & 3) ---
    path('auth/login/', MultiBankLoginView.as_view(), name='login'),  # Sharded prefix login router
    path('auth/register-universal/', UniversalRegistrationView.as_view(), name='register_universal'),  # Global Sign-up + Wallet
    path('auth/enroll-bank/', BankEnrollmentView.as_view(), name='enroll_bank'),  # Existing Matricule Multi-bank signup
    
    # --- Administrative Overrides (Module 3 - Member 3) ---
    path('auth/unblock/<str:matricule>/', AdminUnblockUserView.as_view(), name='admin_unblock_user'),  # Unlocks 3-strike locked users

    # --- Transactions (Modules 4 & 5 - Member 4 & Yourself) ---
    path('transactions/transfer/', TransferCreateView.as_view(), name='transfer_create'),
    path('transactions/withdraw/', WithdrawalCreateView.as_view(), name='withdraw_create'),
    path('transactions/deposit/', DepositCreateView.as_view(), name='deposit_create'), # 👈 Nouvelle route pour alimenter une banque via MoMo

    # --- Information & Discovery ---
    path('accounts/<uuid:account_id>/', AccountDetailView.as_view(), name='account_detail'),
    path('accounts/user/<str:matricule>/', UserAccountsListView.as_view(), name='user_accounts_list'),
    path('accounts/balance/local/<str:matricule>/', LocalAccountBalanceView.as_view(), name='local_account_balance'),

    # ---- Transaction History & Traceability (Module 5 - Yourself) ---
    path('account/history/', TransactionHistoryView.as_view(), name='transaction-history'),
    path('account/history/trace/<str:matricule>/', TraceTransactionHistoryView.as_view(), name='trace-history-by-matricule'),
]