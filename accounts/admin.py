from django.contrib import admin
from .models import Bank, BankUser, Account, Deposit, Transfer, Withdrawal

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(BankUser)
class BankUserAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'full_name', 'email', 'phone', 'user_type', 'status', 'created_at')
    search_fields = ('matricule', 'full_name', 'email', 'phone')
    list_filter = ('user_type', 'status', 'created_at')
    readonly_fields = ('matricule', 'created_at', 'failed_login_attempts')
    ordering = ('-created_at',)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_id', 'owner_link', 'bank_badge', 'formatted_balance', 'created_at')
    search_fields = ('account_id', 'owner__full_name', 'owner__matricule', 'bank__name', 'bank__code')
    list_filter = ('bank', 'created_at')
    raw_id_fields = ('owner', 'bank')  # Évite le chargement lourd des menus déroulants
    ordering = ('bank', '-created_at')

    def owner_link(self, obj):
        return f"{obj.owner.full_name} ({obj.owner.matricule})"
    owner_link.short_description = "Propriétaire"

    def bank_badge(self, obj):
        return obj.bank.code
    bank_badge.short_description = "Banque"

    def formatted_balance(self, obj):
        return f"{obj.balance:,} FCFA".replace(",", " ")
    formatted_balance.short_description = "Solde"


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'sender_bank', 'receiver_bank', 'formatted_amount', 'formatted_fee', 'timestamp', 'description')
    list_filter = ('timestamp', 'sender__bank', 'receiver__bank')
    search_fields = ('transaction_id', 'sender__account_id', 'receiver__account_id', 'sender__owner__matricule', 'receiver__owner__matricule')
    readonly_fields = ('transaction_id', 'timestamp', 'fee')
    raw_id_fields = ('sender', 'receiver')  # Optimisation de recherche d'ID sur PostgreSQL Neon
    ordering = ('-timestamp',)

    def sender_bank(self, obj):
        return f"{obj.sender.owner.matricule} [{obj.sender.bank.code}]"
    sender_bank.short_description = "Émetteur"

    def receiver_bank(self, obj):
        return f"{obj.receiver.owner.matricule} [{obj.receiver.bank.code}]"
    receiver_bank.short_description = "Bénéficiaire"

    def formatted_amount(self, obj):
        return f"{obj.amount:,} FCFA".replace(",", " ")
    formatted_amount.short_description = "Montant"

    def formatted_fee(self, obj):
        return f"{obj.fee:,} FCFA".replace(",", " ")
    formatted_fee.short_description = "Frais"


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """
    Suivi des retraits (Flux sortant d'une banque vers le Hub Central MoMo)
    """
    list_display = ('transaction_id', 'account_link', 'formatted_amount', 'formatted_fee', 'timestamp', 'description')
    list_filter = ('timestamp', 'account__bank')
    search_fields = ('transaction_id', 'account__account_id', 'account__owner__matricule')
    readonly_fields = ('transaction_id', 'timestamp', 'fee')
    raw_id_fields = ('account',)
    ordering = ('-timestamp',)

    def account_link(self, obj):
        return f"{obj.account.owner.matricule} [{obj.account.bank.code}]"
    account_link.short_description = "Compte Débité"

    def formatted_amount(self, obj):
        return f"{obj.amount:,} FCFA".replace(",", " ")
    formatted_amount.short_description = "Montant Transféré"

    def formatted_fee(self, obj):
        return f"{obj.fee:,} FCFA".replace(",", " ")
    formatted_fee.short_description = "Frais"


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    """
    Suivi des dépôts (Flux entrant du Hub Central MoMo vers une banque commerciale)
    """
    list_display = ('transaction_id', 'account_link', 'formatted_amount', 'timestamp', 'description')
    list_filter = ('timestamp', 'account__bank')
    search_fields = ('transaction_id', 'account__account_id', 'account__owner__matricule')
    readonly_fields = ('transaction_id', 'timestamp')
    raw_id_fields = ('account',)
    ordering = ('-timestamp',)

    def account_link(self, obj):
        return f"{obj.account.owner.matricule} [{obj.account.bank.code}]"
    account_link.short_description = "Compte Crédité"

    def formatted_amount(self, obj):
        return f"{obj.amount:,} FCFA".replace(",", " ")
    formatted_amount.short_description = "Montant Injecté"