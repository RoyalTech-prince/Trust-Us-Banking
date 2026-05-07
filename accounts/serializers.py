from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import BankUser, Account, Bank, Transfer, Withdrawal

# ─── 1. CORE MODELS SERIALIZERS ───

class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ['name', 'code']

class AccountSerializer(serializers.ModelSerializer):
    bank = BankSerializer(read_only=True)
    class Meta:
        model = Account
        fields = ['account_id', 'bank', 'balance', 'created_at']

# ─── 2. UNIVERSAL REGISTRATION (The "Identity" Serializer) ───

class UniversalRegistrationSerializer(serializers.ModelSerializer):
    """
    Handles creating a brand new Universal User AND their first Bank Account.
    """
    bank_code = serializers.CharField(write_only=True, help_text="UBC, AFB, or ECO")
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = BankUser
        fields = ['matricule', 'full_name', 'email', 'phone', 'user_type', 'bank_code', 'password']
        read_only_fields = ['matricule']

    def create(self, validated_data):
        bank_code = validated_data.pop('bank_code')
        raw_password = validated_data.pop('password')

        try:
            target_bank = Bank.objects.get(code=bank_code)
        except Bank.DoesNotExist:
            raise serializers.ValidationError({"bank_code": "This bank does not exist in our ecosystem."})

        # 1. Create the Universal Identity (Matricule is auto-generated in model save)
        user = BankUser.objects.create(**validated_data)

        # 2. Create the first Account for this identity
        Account.objects.create(
            owner=user,
            bank=target_bank,
            password=make_password(raw_password), # Hash the bank-specific password
            balance=500.00 # Default opening balance
        )
        return user

# ─── 3. BANK ENROLLMENT (Existing User joining a new Bank) ───

class BankEnrollmentSerializer(serializers.Serializer):
    """
    For users who already have a Matricule but want an account in another bank.
    """
    matricule = serializers.CharField()
    bank_code = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def create(self, validated_data):
        try:
            user = BankUser.objects.get(matricule=validated_data['matricule'])
            bank = Bank.objects.get(code=validated_data['bank_code'])
        except (BankUser.DoesNotExist, Bank.DoesNotExist):
            raise serializers.ValidationError("User or Bank not found.")

        # Check if they already have an account here (UniqueTogether check)
        if Account.objects.filter(owner=user, bank=bank).exists():
            raise serializers.ValidationError(f"User already has an account at {bank.name}.")

        account = Account.objects.create(
            owner=user,
            bank=bank,
            password=make_password(validated_data['password']),
            balance=500.00
        )
        return account

# ─── 4. TRANSACTION SERIALIZERS ───

class AccountInfoSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    bank_code = serializers.CharField(source='bank.code', read_only=True)

    class Meta:
        model = Account
        fields = ['account_id', 'owner_name', 'bank_name', 'bank_code']

class TransferSerializer(serializers.ModelSerializer):
    # Keep these for input (write_only)
    sender_account_id = serializers.UUIDField(write_only=True)
    receiver_matricule = serializers.CharField(write_only=True)
    receiver_bank_code = serializers.CharField(write_only=True)
    
    # New fields for the response (read_only)
    sender_details = AccountInfoSerializer(source='sender', read_only=True)
    receiver_details = AccountInfoSerializer(source='receiver', read_only=True)
    
    class Meta:
        model = Transfer
        fields = [
            'transaction_id', 'amount', 'fee', 'timestamp', 
            'sender_account_id', 'receiver_matricule', 'receiver_bank_code',
            'sender_details', 'receiver_details'
        ]
        read_only_fields = ['transaction_id', 'timestamp', 'fee', 'sender_details', 'receiver_details']
    
    def create(self, validated_data):
        try:
            sender_acc = Account.objects.get(account_id=validated_data.pop('sender_account_id'))
            receiver_acc = Account.objects.get(
                owner__matricule=validated_data.pop('receiver_matricule'),
                bank__code=validated_data.pop('receiver_bank_code')
            )
        except Account.DoesNotExist:
            raise serializers.ValidationError("Target account not found in the ecosystem.")
        
        transfer = Transfer(
            sender=sender_acc,
            receiver=receiver_acc,
            amount=validated_data['amount']
        )
        
        try:
            transfer.save() 
            return transfer
        except ValueError as e:
            raise serializers.ValidationError(str(e))

class WithdrawalSerializer(serializers.ModelSerializer):
    account_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Withdrawal
        fields = ['transaction_id', 'amount', 'fee', 'timestamp', 'account_id']
        read_only_fields = ['transaction_id', 'timestamp', 'fee']
    
    def create(self, validated_data):
        try:
            account = Account.objects.get(account_id=validated_data.pop('account_id'))
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account does not exist.")
        
        withdrawal = Withdrawal(account=account, amount=validated_data['amount'])
        
        try:
            withdrawal.save()
            return withdrawal
        except ValueError as e:
            raise serializers.ValidationError(str(e))

class AccountBalanceSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    matricule = serializers.CharField(source='owner.matricule', read_only=True)
    
    class Meta:
        model = Account
        fields = ['account_id', 'owner_name', 'matricule', 'bank_name', 'balance', 'created_at']

class BankUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankUser
        fields = ['matricule', 'full_name', 'email', 'phone', 'user_type', 'created_at']
        read_only_fields = ['matricule', 'created_at']

    def update(self, instance, validated_data):
        # Allow updating email and phone, but keep matricule permanent
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.save()
        return instance