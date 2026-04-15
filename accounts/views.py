from rest_framework import generics, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema

from .models import BankUser
from .serializers import UserSerializer, CreateUserSerializer, LoginRequestSerializer
from .utils import verify_face 

# --- 1. USER MANAGEMENT (Add & List) ---
class UserListCreateView(generics.ListCreateAPIView):
    queryset = BankUser.objects.all()
    serializer_class = UserSerializer
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['User Management'],
        request=CreateUserSerializer,
        responses={201: UserSerializer},
        description="Create a new bank user with an optional face sample photo."
    )
    def post(self, request, *args, **kwargs):
        serializer = CreateUserSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            balance = serializer.validated_data.get('balance', 0.00)
            face_image = request.FILES.get('face_encoding_sample')
            
            user = BankUser.objects.create_user(
                username=username,
                password=password,
                balance=balance,
                face_encoding_sample=face_image
            )
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- 2. BANKING OPERATIONS ---
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Banking Operations'])
    def get(self, request):
        user = request.user
        if user.has_active_license():
            return Response({
                "username": user.username,
                "balance": user.balance,
                "license_status": "Active"
            }, status=status.HTTP_200_OK)
        return Response({"error": "License expired"}, status=status.HTTP_403_FORBIDDEN)


# --- 3. AUTHENTICATION (Flexible Login) ---
class FlexibleLoginView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Authentication'],
        request=LoginRequestSerializer,
        responses={200: serializers.DictField()},
        description="Login using either a password OR a face image upload."
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        face_image = request.FILES.get('face_image')

        try:
            user = BankUser.objects.get(username=username)
        except BankUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        authenticated = False
        login_method = None

        # 1. Check Password first
        if password:
            user_auth = authenticate(username=username, password=password)
            if user_auth:
                authenticated = True
                login_method = "password"

        # 2. Check Face ONLY if password failed or wasn't provided
        if not authenticated and face_image:
            if not user.face_encoding_sample:
                return Response({"error": "No face sample on file for this user"}, status=status.HTTP_400_BAD_REQUEST)
            
            # --- FIX APPLIED HERE ---
            # We use .url because the file is on Cloudinary, not on your local disk.
            try:
                # We fetch the URL. Note: Cloudinary handles the HTTPS link automatically.
                stored_url = user.face_encoding_sample.url
                is_match = verify_face(stored_url, face_image)
                
                if is_match:
                    authenticated = True
                    login_method = "facial_recognition"
                else:
                    return Response({"error": "Face verification failed. Access denied."}, status=status.HTTP_401_UNAUTHORIZED)
            except ValueError:
                return Response({"error": "Problem accessing stored face sample."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. Final Authorization Check
        if authenticated:
            if user.has_active_license():
                return Response({
                    "message": "Access Granted",
                    "balance": str(user.balance),
                    "method": login_method
                }, status=status.HTTP_200_OK)
            return Response({"error": "License expired"}, status=status.HTTP_403_FORBIDDEN)
        
        return Response({"error": "Authentication failed. Provide valid password or face."}, status=status.HTTP_401_UNAUTHORIZED)