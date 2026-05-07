from django.contrib import admin
from .models import Bank, BankUser, Account, Transfer, Withdrawal

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(BankUser)
class BankUserAdmin(admin.ModelAdmin):
    # Only use fields that actually exist in your new BankUser model
    list_display = ('matricule', 'full_name', 'email', 'phone', 'user_type', 'created_at')
    search_fields = ('matricule', 'full_name', 'email')
    list_filter = ('user_type', 'created_at')
    readonly_fields = ('matricule', 'created_at')

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_id', 'owner', 'bank', 'balance', 'created_at')
    search_fields = ('owner__full_name', 'owner__matricule', 'bank__name')
    list_filter = ('bank', 'created_at')

@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'sender', 'receiver', 'amount', 'fee', 'timestamp')
    readonly_fields = ('transaction_id', 'timestamp', 'fee')

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'account', 'amount', 'fee', 'timestamp')
    readonly_fields = ('transaction_id', 'timestamp', 'fee')