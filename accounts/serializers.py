from rest_framework import serializers
from .models import BankUser, Account


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