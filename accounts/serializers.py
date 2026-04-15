from rest_framework import serializers
from .models import BankUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankUser
        fields = ['id', 'username', 'password', 'balance', 'face_encoding_sample']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        # We use create_user so the password gets hashed properly
        return BankUser.objects.create_user(**validated_data)

class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'})
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0.00)
    # Use FileField + label to force the "Choose File" button in Swagger
    face_encoding_sample = serializers.FileField(
        required=False, 
        label="Upload Face Image"
    )
    
class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=False, allow_blank=True)
    # This triggers the 'Choose File' button for the login attempt
    face_image = serializers.FileField(required=False, label="Login Face Photo")