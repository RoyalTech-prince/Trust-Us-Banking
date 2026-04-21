from argparse import Action
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import BankUser, Transfer, Withdrawal, Account
from .serializers import BankUserSerializer, TransferSerializer, WithdrawalSerializer, AccountBalanceSerializer


@extend_schema(tags=['Users'])
class BankUserViewSet(viewsets.ModelViewSet):
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']


@extend_schema(tags=['Transactions'])
class TransferViewSet(viewsets.ModelViewSet):
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    http_method_names = ['get', 'post']
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                {
                    "status": "success",
                    "message": "Transfer completed successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(tags=['Transactions'])
class WithdrawalViewSet(viewsets.ModelViewSet):
    queryset = Withdrawal.objects.all()
    serializer_class = WithdrawalSerializer
    http_method_names = ['get', 'post']
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                {
                    "status": "success",
                    "message": "Withdrawal completed successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
@extend_schema(tags=['Accounts'])
class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountBalanceSerializer
    
    @extend_schema(
        description="Get account balance by username",
        responses={200: AccountBalanceSerializer}
    )
    @action(detail=False, methods=['get'], url_path='balance/(?P<username>[^/.]+)')
    def get_balance(self, request, username=None):
        try:
            account = Account.objects.get(owner__username=username)
            serializer = self.get_serializer(account)
            return Response({
                "status": "success",
                "data": serializer.data
            })
        except Account.DoesNotExist:
            return Response({
                "status": "error",
                "message": f"Account for user '{username}' does not exist."
            }, status=status.HTTP_404_NOT_FOUND)