from django.contrib import admin
from .models import BankUser, Account, Transfer, Withdrawal

@admin.register(BankUser)
class BankUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'user_type', 'is_staff')

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('owner', 'balance', 'created_at')
    readonly_fields = ('account_id', 'created_at')

@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'amount', 'timestamp')
    readonly_fields = ('transaction_id', 'timestamp')

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('account', 'amount', 'timestamp')
    readonly_fields = ('transaction_id', 'timestamp')