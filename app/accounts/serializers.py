
from rest_framework import serializers
from .models import User, Tier, Subscription, Payment
from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import  smart_bytes, force_str
from django.urls import reverse
from .tasks import send_normal_email
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .tasks import send_code_to_user


def create_reset_link(user):
    uidb64 = urlsafe_base64_encode(smart_bytes(user.id))
    token = PasswordResetTokenGenerator().make_token(user)
    site_domain = 'https://swiftsuite.app'
    relative_link = reverse('password_reset_confirm', kwargs={'uidb64':uidb64, 'token':token})
    abslink = f'{site_domain}{relative_link}'
    data = {
        'reset_link':abslink,
        'email_subject':'Reset your password',
        "to_email":user.email,
        'first_name':user.first_name
    }

    send_normal_email.delay(data)

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length = 68, min_length = 6, write_only = True)
    password2 = serializers.CharField(max_length = 68, min_length = 6, write_only = True)


    class Meta:
        model = User
        fields =["email", "first_name", "last_name", "password", "password2"]

    def validate(self, attrs):
        password = attrs.get('password', '')
        password2 = attrs.get('password2', '')
        if password != password2:
            raise serializers.ValidationError("Passwords do not match")

        return attrs
    
    def create(self, validated_data):
        user = User.objects.create_user(
            email = validated_data['email'],
            first_name = validated_data['first_name'],
            last_name = validated_data['last_name'],
            password = validated_data['password'],

        )
        return user
    
class VerifyEmailSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)  # Assuming OTP is a 6-digit code

    

class LoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length = 255, min_length = 6)
    password = serializers.CharField(max_length = 65, write_only = True)
    full_name = serializers.CharField(max_length = 255, read_only = True)
    access_token = serializers.CharField(max_length = 255, read_only = True)
    refresh_token = serializers.CharField(max_length = 255, read_only = True)
    isAdmin = serializers.BooleanField(read_only = True)
    subscribed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = ["id", "email", "password", "full_name", "isAdmin", "subscribed", "access_token", "refresh_token"]
        
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        request = self.context.get('request')
        user = authenticate(request, email=email, password=password)
        if not user:
            raise AuthenticationFailed('Invalid credentials try again')
        if not user.is_verified:
            # resend an otp to the user for verification
            send_code_to_user(user.email)
            raise AuthenticationFailed('Account not verified, check your email for verification code')

        user_token = user.tokens()

        return {
            'id':user.id,
            "email":user.email,
            'full_name':user.get_full_name,
            "isAdmin": user.is_staff,
            "subscribed": user.subscribed,
            'access_token':user_token.get('access'),
            'refresh_token':user_token.get('refresh'),
        }


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length = 255)

    class Meta:
        fields = ['email']

    def validate(self, attrs):
        email = attrs.get('email')
        if User.objects.filter(email = email).exists():
            user = User.objects.get(email = email)
            create_reset_link(user)
        else:
            raise serializers.ValidationError("User with this email does not exist")
        return super().validate(attrs)


class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length = 100, min_length = 6, write_only = True )
    confirm_password = serializers.CharField(max_length = 100, min_length = 6, write_only = True )
    uidb64 = serializers.CharField(write_only = True)
    token = serializers.CharField(write_only = True)

    class Meta:
        fields = ['password', 'confirm_password', 'uidb64', 'token']

    def validate(self, attrs):
        try:
            token = attrs.get('token')
            uidb64 = attrs.get('uidb64')
            password = attrs.get('password')
            confirm_password = attrs.get('confirm_password')

            user_id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id = user_id)
            if not PasswordResetTokenGenerator().check_token(user, token):
                raise AuthenticationFailed("reset link is invalid or has expired", 401)
            
            if password != confirm_password:
                raise AuthenticationFailed("password do not match")
            
            user.set_password(password)
            user.is_verified = True
            user.save()

            return user
        
        except Exception as e:
            return AuthenticationFailed('link is invalid or has expired')
        

class LogoutUserSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    default_error_message = {
        "bad_token":'Token is invalid or has expired'
    }

    def validate(self, attrs):
        self.token = attrs.get('refresh_token')
        return attrs
    
    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except TokenError:
            return self.fail('bad_token')

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'profile_image']
        read_only_fields = ['email']

class ChangePasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)
    
    def validate(self, data):
        """Validate the new password and confirm password."""
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")
        
        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        return data
        
class RegisterSubaccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=100, min_length=6, write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'password']

    def validate(self, attrs):
        email = attrs.get('email')
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('Email is already in use')
        return attrs

    def create(self, validated_data):
        parent = self.context['request'].user
        validated_data['parent'] = parent

        user = User.objects.create_user(**validated_data)
        create_reset_link(user)
        return user
    
class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = "__all__"
        
class SubscriptionSerializer(serializers.ModelSerializer):
    tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())
    class Meta:
        model = Subscription
        fields = ['tier']
        
    
class PaymentSerializer(serializers.ModelSerializer):
    expires_at = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = "__all__"
        
    def get_expires_at(self, obj):
        subscription = getattr(obj.user, "tier_subscription", None)
        if subscription and subscription.is_active():
            return subscription.expires_at
        return None