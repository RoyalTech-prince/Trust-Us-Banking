from django.contrib import admin
from .models import BankUser, Account, Transfer, Withdrawal


@admin.register(BankUser)
class BankUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'user_type', 'phone', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'phone')
    readonly_fields = ('user_id', 'date_joined', 'last_login')
    fieldsets = (
        ('User Information', {
            'fields': ('username', 'email', 'phone', 'user_type')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login')
        }),
        ('System', {
            'fields': ('user_id',)
        }),
    )


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('owner', 'balance', 'created_at', 'account_id')
    list_filter = ('created_at',)
    search_fields = ('owner__username', 'owner__email')
    readonly_fields = ('account_id', 'created_at')
    ordering = ('-created_at',)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('get_sender_username', 'get_receiver_username', 'amount', 'timestamp', 'transaction_id')
    list_filter = ('timestamp',)
    search_fields = ('sender__owner__username', 'receiver__owner__username')
    readonly_fields = ('transaction_id', 'timestamp')
    ordering = ('-timestamp',)
    
    def get_sender_username(self, obj):
        return obj.sender.owner.username
    get_sender_username.short_description = 'Sender'
    
    def get_receiver_username(self, obj):
        return obj.receiver.owner.username
    get_receiver_username.short_description = 'Receiver'


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('get_account_username', 'amount', 'timestamp', 'transaction_id')
    list_filter = ('timestamp',)
    search_fields = ('account__owner__username',)
    readonly_fields = ('transaction_id', 'timestamp')
    ordering = ('-timestamp',)
    
    def get_account_username(self, obj):
        return obj.account.owner.username
    get_account_username.short_description = 'Account Owner'