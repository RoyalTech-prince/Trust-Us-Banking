import uuid
from django.db import models, transaction
from datetime import datetime
from decimal import Decimal
from django.conf import settings

# ─── CRITICAL CORRECTION: ADD MISSING HASHING IMPORTS ───
from django.contrib.auth.hashers import make_password, check_password as django_check_password

class Bank(models.Model):
    name = models.CharField(max_length=100, unique=True) # UBC, AfrilandFirst, Ecobank
    code = models.CharField(max_length=10, unique=True) # e.g., UBC, AFB, ECO

    def __str__(self):
        return f"{self.name} ({self.code})"


class BankUser(models.Model):
    class UserType(models.TextChoices):
        ADMIN  = 'admin',  'Bank Administrator'
        CLIENT = 'client', 'Client User'

    class AccountStatus(models.TextChoices):
        ACTIVE  = 'ACTIVE',  'Active'
        BLOCKED = 'BLOCKED', 'Blocked'

    # Universal Identity Fields
    matricule  = models.CharField(max_length=20, unique=True, editable=False)
    full_name  = models.CharField(max_length=255)
    email      = models.EmailField(unique=True)
    phone      = models.CharField(max_length=20, unique=True)
    user_type  = models.CharField(max_length=10, choices=UserType.choices, default=UserType.CLIENT)
    
    # Password Field explicitly handled
    password   = models.CharField(max_length=128)
    
    # Security tracking fields mapping to MultiBankLoginView
    status                = models.CharField(max_length=10, choices=AccountStatus.choices, default=AccountStatus.ACTIVE)
    failed_login_attempts = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        """Hashes the password before writing to the database."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifies the password incoming from the login endpoint."""
        return django_check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        if not self.matricule:
            year = datetime.now().year
            prefix = f"RT{year}"
            
            last_user = BankUser.objects.filter(matricule__startswith=prefix).order_by('-matricule').first()
            
            if last_user:
                last_number = int(last_user.matricule[6:])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"
            
            self.matricule = f"{prefix}{new_number}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.matricule} ({self.get_user_type_display()})"


class Account(models.Model):
    account_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner      = models.ForeignKey(BankUser, on_delete=models.CASCADE, related_name='accounts')
    bank       = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='accounts')
    password   = models.CharField(max_length=128) 
    balance    = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'bank')

    def __str__(self):
        return f"{self.bank.name} Account: {self.owner.matricule} (Bal: {self.balance})"


class Transaction(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp      = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Transfer(Transaction):
    sender   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_sent')
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_received')
    fee      = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # Set structural fees based on clearing router distance
            self.fee = Decimal('10.00') if self.sender.bank == self.receiver.bank else Decimal('50.00')
            
            # ─── FIX: EXECUTE AND VALIDATE BALANCES BEFORE COMMITTING TRANSFER RECORD ───
            self.execute() 
            
        super().save(*args, **kwargs)

    def execute(self):
        with transaction.atomic():
            sender_acc = Account.objects.select_for_update().get(pk=self.sender.pk)
            receiver_acc = Account.objects.select_for_update().get(pk=self.receiver.pk)
            
            total = self.amount + self.fee
            if sender_acc.balance < total:
                raise ValueError("Solde insuffisant pour effectuer ce virement (Frais inclus).")
            
            sender_acc.balance -= total
            receiver_acc.balance += self.amount
            sender_acc.save()
            receiver_acc.save()


class Withdrawal(Transaction):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='withdrawals')
    fee     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # ─── FIX: EXECUTE AND VALIDATE BALANCES BEFORE COMMITTING WITHDRAWAL RECORD ───
            self.execute()
        super().save(*args, **kwargs)

    def execute(self):
        with transaction.atomic():
            acc = Account.objects.select_for_update().get(pk=self.account.pk)
            total = self.amount + self.fee
            if acc.balance < total:
                raise ValueError("Solde insuffisant pour effectuer ce retrait.")
            acc.balance -= total
            acc.save()