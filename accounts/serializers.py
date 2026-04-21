from rest_framework import serializers
from .models import BankUser, Account
from .models import Transfer, Withdrawal


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Account
        fields = ['account_id', 'balance', 'created_at']


class BankUserSerializer(serializers.ModelSerializer):
    account   = AccountSerializer(read_only=True)
    password  = serializers.CharField(write_only=True)

    class Meta:
        model  = BankUser
        fields = ['id', 'user_id', 'username', 'email', 'phone', 'user_type', 'password', 'account']
        read_only_fields = ['user_id', 'user_type']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = BankUser(**validated_data)
        user.set_password(password)
        user.user_type = BankUser.UserType.CUSTOMER  # hardcoded for now
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class TransferSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(write_only=True)
    receiver_username = serializers.CharField(write_only=True)
    
    class Meta:
        model = Transfer
        fields = ['transaction_id', 'amount', 'timestamp', 'sender_username', 'receiver_username']
        read_only_fields = ['transaction_id', 'timestamp']
    
    def create(self, validated_data):
        sender_username = validated_data.pop('sender_username')
        receiver_username = validated_data.pop('receiver_username')
        
        try:
            sender_account = Account.objects.get(owner__username=sender_username)
            receiver_account = Account.objects.get(owner__username=receiver_username)
        except Account.DoesNotExist:
            raise serializers.ValidationError("One or both accounts do not exist.")
        
        transfer = Transfer(
            sender=sender_account,
            receiver=receiver_account,
            amount=validated_data['amount']
        )
        
        try:
            transfer.save()  # This will trigger execute() via the save override
            return transfer
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class WithdrawalSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    
    class Meta:
        model = Withdrawal
        fields = ['transaction_id', 'amount', 'timestamp', 'username']
        read_only_fields = ['transaction_id', 'timestamp']
    
    def create(self, validated_data):
        username = validated_data.pop('username')
        
        try:
            account = Account.objects.get(owner__username=username)
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account does not exist.")
        
        withdrawal = Withdrawal(
            account=account,
            amount=validated_data['amount']
        )
        
        try:
            withdrawal.save()  # This will trigger execute() via the save override
            return withdrawal
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        
class AccountBalanceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='owner.username', read_only=True)
    email = serializers.EmailField(source='owner.email', read_only=True)
    
    class Meta:
        model = Account
        fields = ['account_id', 'username', 'email', 'balance', 'created_at']
        read_only_fields = ['account_id', 'balance', 'created_at']