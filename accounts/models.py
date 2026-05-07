import uuid
from django.db import models, transaction
from datetime import datetime
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

class Bank(models.Model):
    name = models.CharField(max_length=100, unique=True) # UBC, AfrilandFirst, Ecobank
    code = models.CharField(max_length=10, unique=True) # e.g., UBC, AFB, ECO

    def __str__(self):
        return f"{self.name} ({self.code})"


class BankUser(models.Model):
    class UserType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        EMPLOYEE = 'employee', 'Employee'
        MANAGER  = 'manager',  'Manager'

    # Universal Identity Fields
    matricule = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=255)
    email     = models.EmailField(unique=True)
    phone     = models.CharField(max_length=20, unique=True)
    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.CUSTOMER)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.matricule:
            year = datetime.now().year
            prefix = f"RT{year}"
            
            # Find the last matricule for this year to handle auto-increment
            last_user = BankUser.objects.filter(matricule__startswith=prefix).order_by('-matricule').first()
            
            if last_user:
                # Extract the last 4 digits, increment, and pad with zeros
                last_number = int(last_user.matricule[6:])
                new_number = str(last_number + 1).zfill(4)
            else:
                new_number = "0001"
            
            self.matricule = f"{prefix}{new_number}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.matricule}"


class Account(models.Model):
    account_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner      = models.ForeignKey(BankUser, on_delete=models.CASCADE, related_name='accounts')
    bank       = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='accounts')
    
    # Store hashed password for this specific bank
    password   = models.CharField(max_length=128) 
    
    balance    = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents a user from having two accounts in the same bank
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
            # FIX: Wrap numbers in Decimal()
            self.fee = Decimal('10.00') if self.sender.bank == self.receiver.bank else Decimal('50.00')
        super().save(*args, **kwargs)
        if is_new:
            self.execute()

    def execute(self):
        with transaction.atomic():
            sender_acc = Account.objects.select_for_update().get(pk=self.sender.pk)
            receiver_acc = Account.objects.select_for_update().get(pk=self.receiver.pk)
            
            # Now both are Decimals, so math will work
            total = self.amount + self.fee
            if sender_acc.balance < total:
                raise ValueError("Insufficient funds")
            
            sender_acc.balance -= total
            receiver_acc.balance += self.amount
            sender_acc.save()
            receiver_acc.save()

class Withdrawal(Transaction):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='withdrawals')
    fee     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.execute()

    def execute(self):
        with transaction.atomic():
            acc = Account.objects.select_for_update().get(pk=self.account.pk)
            total = self.amount + self.fee
            if acc.balance < total:
                raise ValueError("Insufficient funds")
            acc.balance -= total
            acc.save()

@receiver(post_save, sender=Account)
def send_welcome_email(sender, instance, created, **kwargs):
    if created:
        user = instance.owner
        bank = instance.bank
        
        subject = f'Welcome to {bank.name}!'
        message = (
            f"Hello {user.full_name},\n\n"
            f"Your account at {bank.name} has been successfully created.\n"
            f"Your Universal Matricule is: {user.matricule}\n"
            f"Your Initial Balance is: {instance.balance} XAF\n\n"
            f"Thank you for choosing Trust-Us-Banking Ecosystem!"
        )
        recipient_list = [user.email]
        
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        except Exception as e:
            print(f"Email failed to send: {e}")