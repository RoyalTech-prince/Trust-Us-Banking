import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver


class BankUser(AbstractUser):

    class UserType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        EMPLOYEE = 'employee', 'Employee'
        MANAGER  = 'manager',  'Manager'

    user_id   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.CUSTOMER)
    email     = models.EmailField(unique=True)
    phone     = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.user_type})"


class Account(models.Model):
    account_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner      = models.OneToOneField(BankUser, on_delete=models.CASCADE, related_name='account')
    balance    = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Account({self.owner.username} - {self.balance})"


class Transaction(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp      = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Transfer(Transaction):
    sender   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_sent')
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_received')

    def execute(self):
        if self.sender.balance < self.amount:
            raise ValueError("Insufficient balance.")
        self.sender.balance   -= self.amount
        self.receiver.balance += self.amount
        self.sender.save()
        self.receiver.save()
        self.save()

    def __str__(self):
        return f"Transfer({self.sender} -> {self.receiver}: {self.amount})"


class Withdrawal(Transaction):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='withdrawals')

    def execute(self):
        if self.account.balance < self.amount:
            raise ValueError("Insufficient balance.")
        self.account.balance -= self.amount
        self.account.save()
        self.save()

    def __str__(self):
        return f"Withdrawal({self.account.owner.username}: {self.amount})"


# ── SIGNAL: auto-create Account when a new BankUser is created ──
@receiver(post_save, sender=BankUser)
def create_account_for_customer(sender, instance, created, **kwargs):
    if created and instance.user_type == BankUser.UserType.CUSTOMER:
        Account.objects.create(owner=instance)