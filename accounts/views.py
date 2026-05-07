from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.hashers import check_password
from django.db import models
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from .models import BankUser, Account, Transfer, Withdrawal
from .serializers import (
    UniversalRegistrationSerializer, 
    BankEnrollmentSerializer,
    TransferSerializer, 
    WithdrawalSerializer,
    AccountBalanceSerializer,
    BankUserSerializer
)

# ─── AUTHENTICATION & LOGIN ───

class MultiBankLoginView(APIView):
    """
    Custom Login: Returns accounts only where the password matches.
    """
    @extend_schema(
        request=inline_serializer(
            name='LoginRequest',
            fields={
                'identifier': serializers.CharField(help_text="Email or Matricule"),
                'password': serializers.CharField(style={'input_type': 'password'})
            }
        ),
        responses={200: inline_serializer(name='LoginRes', fields={'message': serializers.CharField(), 'authorized_accounts': serializers.ListField()})}
    )
    def post(self, request):
        identifier = request.data.get('identifier')
        password = request.data.get('password')

        if not identifier or not password:
            return Response({"error": "Missing credentials"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = BankUser.objects.filter(
                models.Q(email=identifier) | models.Q(matricule=identifier)
            ).first()
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response({"error": "Query failed"}, status=status.HTTP_400_BAD_REQUEST)

        all_accounts = Account.objects.filter(owner=user).select_related('bank')
        matched_accounts = []

        for account in all_accounts:
            if check_password(password, account.password):
                matched_accounts.append({
                    "account_id": str(account.account_id),
                    "bank_name": account.bank.name,
                    "balance": float(account.balance),
                    "matricule": user.matricule
                })

        if not matched_accounts:
            return Response({"error": "Invalid password for any bank"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({
            "message": "Login successful",
            "user_full_name": user.full_name,
            "authorized_accounts": matched_accounts
        }, status=status.HTTP_200_OK)


# ─── UNIVERSAL USER CRUD & REGISTRATION ───

class UniversalRegistrationView(generics.CreateAPIView):
    """Register a new human and their first bank account."""
    serializer_class = UniversalRegistrationSerializer

class BankUserListView(generics.ListAPIView):
    """List all Universal Users in the system."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer

class BankUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Read, Update, or Delete a Universal User by Matricule."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer
    lookup_field = 'matricule'


# ─── BANK ENROLLMENT ───

class BankEnrollmentView(APIView):
    """Link an existing matricule to a new bank."""
    @extend_schema(request=BankEnrollmentSerializer)
    def post(self, request):
        serializer = BankEnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Enrolled successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── TRANSACTIONS ───

class TransferCreateView(generics.CreateAPIView):
    serializer_class = TransferSerializer

class WithdrawalCreateView(generics.CreateAPIView):
    serializer_class = WithdrawalSerializer


# ─── ACCOUNT INFORMATION ───

class AccountDetailView(generics.RetrieveAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountBalanceSerializer
    lookup_field = 'account_id'

class UserAccountsListView(APIView):
    @extend_schema(responses={200: AccountBalanceSerializer(many=True)})
    def get(self, request, matricule):
        accounts = Account.objects.filter(owner__matricule=matricule)
        serializer = AccountBalanceSerializer(accounts, many=True)
        return Response(serializer.data)