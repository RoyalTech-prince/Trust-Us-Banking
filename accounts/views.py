from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import BankUser
from .serializers import BankUserSerializer


@extend_schema(tags=['Users'])
class BankUserViewSet(viewsets.ModelViewSet):
    queryset           = BankUser.objects.all()
    serializer_class   = BankUserSerializer
    http_method_names  = ['get', 'post', 'put', 'patch', 'delete']