
from rest_framework.generics import GenericAPIView
from .serializers import UserRegisterSerializer, LoginSerializer, PasswordResetSerializer,SetNewPasswordSerializer, LogoutUserSerializer, VerifyEmailSerializer, TierSerializer, SubscriptionSerializer, RegisterSubaccountSerializer, PaymentSerializer, UserProfileSerializer, ChangePasswordSerializer, SubAccountPermissionsSerializer, ManageSubAccountSerializer
from rest_framework.response import Response
from rest_framework import status
from .tasks import send_code_to_user
from .models import OneTimePassword, User, Tier, Subscription, Payment, SubAccountPermissions
from django.utils.encoding import smart_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponseRedirect
from rest_framework.decorators import api_view
import stripe
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.utils import timezone
from vendorEnrollment.pagination import CustomOffsetPagination
from rest_framework.viewsets import ModelViewSet
from .permissions import CanCreateSubaccount, IsOwnerOrHasPermission
from vendorActivities.permission import IsSuperUser
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied


stripe.api_key = settings.STRIPE_SECRET_KEY 

class RegisterUserView(GenericAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user_data = request.data 
        serializer = self.serializer_class(data=user_data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            user = serializer.data
            # send email
            send_code_to_user(user['email'])

            return Response({
                "data":user, 
                'message':"Sign up succesfull", 
                }, status=status.HTTP_201_CREATED) 
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SendOTP(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        email = request.data['email']
        try:
            user = User.objects.get(email=email)
            if not user.is_verified:
                send_code_to_user.delay(email)
                return Response({"message":"code sent to your email"}, status=status.HTTP_200_OK)
            return Response({"message":"user already verified"}, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({"message":"user does not exist"}, status=status.HTTP_404_NOT_FOUND)

class ManageUser(GenericAPIView):
    permission_classes = [IsSuperUser]
    def get(self, request, pk=None):
        if pk:
            try:
                user = User.objects.get(pk=pk)
                serializer = UserProfileSerializer(user)
                return Response(serializer.data)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=404)
        else:
            users = User.objects.all()
            serializer = UserProfileSerializer(users, many=True)
            return Response(serializer.data)   

    def delete(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)          
    
class VerifyUserEmail(GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otpcode = serializer.validated_data.get('otp')
        

        try:
            user_code_obj = OneTimePassword.objects.get(code=otpcode)
            user = user_code_obj.user
            if not user.is_verified:
                user.is_verified = True
                user.save()
                return Response({
                    "message": "account email verified successfully"
                }, status=status.HTTP_200_OK)
            return Response({
                "message": "Code is valid, but the user's email has already been verified."
            }, status=status.HTTP_204_NO_CONTENT)
        except OneTimePassword.DoesNotExist:
            return Response({"message": "Passcode not provided"}, status=status.HTTP_404_NOT_FOUND)

class LoginUserView(GenericAPIView):
    serializer_class  = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context = {'request':request})
        serializer.is_valid(raise_exception=True)
        return Response (serializer.data, status=status.HTTP_200_OK)

class ChangePasswordView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            old_password = serializer.validated_data['password']
            new_password = serializer.validated_data['new_password']
            user = request.user
            if not user.check_password(old_password):
                return Response({"error": "Invalid password"}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.save()
            return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetView(GenericAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        serializer = self.serializer_class(data = request.data, context ={'request':request})
        serializer.is_valid(raise_exception = True)
     
        return Response({'message':"A link has been sent to your email to reset your password"}, status=status.HTTP_200_OK)
    
class PasswordResetConfirm(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get(self, request, uidb64, token):
        try:
            user_id = smart_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=user_id)
            if not PasswordResetTokenGenerator().check_token(user, token):
                return Response({'message':'Token is invalid or has expired'}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({'success':True, 'message':'credential is valid', 'uidb64':uidb64, 'token':token}, status=status.HTTP_200_OK)
        
        except DjangoUnicodeDecodeError:
            return Response({'message':'Token is invalid or has expired'}, status=status.HTTP_401_UNAUTHORIZED)
        
class SetNewPassword(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    serializer_class = SetNewPasswordSerializer
    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'message':'Password reset successful'}, status=status.HTTP_200_OK)
    

class LogoutUserView(GenericAPIView):
    serializer_class = LogoutUserSerializer
    permission_classes = [IsAuthenticated]
    

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
def landingPage(request):
    # return HttpResponseRedirect("https://swift-suite.netlify.app/layout/home")
    return HttpResponseRedirect("https://swiftsuite.app")
    # return render(request, "index.html")

class UserProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get(self, request):
        serializer = self.serializer_class(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = self.serializer_class(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

class RegisterSubaccountView(GenericAPIView):
    serializer_class = RegisterSubaccountSerializer
    permission_classes = [IsAuthenticated, CanCreateSubaccount]

    def post(self, request):
        user_data = request.data 
        serializer = self.serializer_class(data=user_data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            user = serializer.data
    
            return Response({
                "data": user, 
                'message': "Subaccount created successfully", 
            }, status=status.HTTP_201_CREATED)

class TierViewSet(ModelViewSet):
    authentication_classes = []
    permission_classes = [IsSuperUser]
    serializer_class = TierSerializer
    queryset = Tier.objects.all()


class SubscriptionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()
    
    def get(self, request):
        try:
            subscription = request.user.tier_subscription
            
            if not subscription.is_active():
                return Response({"detail": "Your subscription has expired."}, status=403)
        
            return Response({
                "tier": subscription.tier.name,
                "subscribed_at": subscription.subscribed_at
            })
        except Subscription.DoesNotExist:
            return Response({"detail": "You are not subscribed to any tier."}, status=404)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        tier = serializer.validated_data['tier']
        
        if request.user.is_subaccount:
             return Response({"detail": "You are not permitted to subscribe with a subaccount"}, status=403)
         
        try:
            subscription = request.user.tier_subscription
            if subscription.is_active() and subscription.tier == tier:
                remaining_days = (subscription.expires_at - timezone.now()).days
                if remaining_days > 5:  #disallow renewal if > 5 days left
                    return Response({
                        "detail": f"You still have {remaining_days} days left on your {tier.name} plan. "
                                f"Renewals are only allowed within 5 days of expiry."
                    }, status=400)
        except Subscription.DoesNotExist:
            pass
        
        existing_payment = Payment.objects.filter(
            user=request.user,
            tier=tier,
            status='pending'
        ).first()

        if existing_payment:
            try:
                checkout_session = stripe.checkout.Session.retrieve(existing_payment.stripe_session_id)
                if checkout_session.status == 'open':
                    return Response({'checkout_url': checkout_session.url}, status=200)

                elif checkout_session.status == 'complete':
                    existing_payment.status = 'paid'
                    existing_payment.save()
                    # Create or update the subscription
                    Subscription.objects.update_or_create(
                        user=request.user,
                        defaults={
                            'tier': tier,
                            'expires_at': timezone.now() + timedelta(days=30)
                        }
                    )
                    request.user.tier = tier
                    request.user.save(update_fields=["tier"])
                    
                    return Response({'message': 'Payment already completed for this tier.'}, status=400)
                
                elif checkout_session.status == 'failed':
                    existing_payment.status = 'failed'
                    existing_payment.save()
                    return Response({'message': 'Payment failed for this tier.'}, status=400)
            except stripe.error.InvalidRequestError:
                pass
            
                
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': tier.name,
                        'description': tier.description,
                    },
                    'unit_amount': int(tier.price * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            customer_email=request.user.email,
            success_url='https://swiftsuite.app/chooseplan/paymentsuccessful/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://swiftsuite.app/chooseplan/paymentfailed/',
            metadata={
                'user_id': request.user.id,
                'tier_id': tier.id
            }
        )
                
        Payment.objects.create(
            user=request.user,
            tier=tier,
            amount=tier.price,
            stripe_session_id=checkout_session.id,
            status='pending'
        )
        
        return Response({'checkout_url': checkout_session.url}, status=200)
    
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return Response({'error': 'Invalid signature or payload'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        tier_id = session['metadata']['tier_id']
        try: 
            user = User.objects.get(id=user_id)
            tier = Tier.objects.get(id=tier_id)

            now = timezone.now()
            subscription = Subscription.objects.filter(user=user).first()

            if subscription:
                if subscription.is_active():
                    if subscription.tier == tier:
                        # Same plan: extend
                        expires_at = subscription.expires_at + timedelta(days=30)
                    else:
                        # Different plan: replace immediately
                        expires_at = now + timedelta(days=30)
                else:
                    # Expired subscription → fresh start
                    expires_at = now + timedelta(days=30)
            else:
                # No subscription → fresh start
                expires_at = now + timedelta(days=30)

            # Create or update the subscription
            Subscription.objects.update_or_create(
                user=user,
                defaults={
                    'tier': tier,
                    'subscribed_at': now,
                    'expires_at': expires_at,
                }
            )

            # Optional: reflect tier directly on user model
            user.tier = tier
            user.save()

            # Update payment status
            Payment.objects.filter(stripe_session_id=session['id']).update(status='paid')
            
        except (User.DoesNotExist, Tier.DoesNotExist):
            return JsonResponse({'error': 'Invalid user or tier in metadata'}, status=400)
        
    return JsonResponse({'status': 'success'}, status=200)

class VerifyCheckoutSessionView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid" and session.customer_email == request.user.email:
                # Confirm payment is in the database
                payment = Payment.objects.filter(
                    user=request.user,
                    stripe_session_id=session_id,
                ).first()

                if payment and payment.status == 'paid':
                    return Response({
                        "status": "success",
                        "tier": payment.tier.name,
                        "amount": payment.amount
                    })

                if payment:
                    # Mark as paid
                    payment.status = 'paid'
                    payment.save(update_fields=["status"])

                    # Get tier from payment
                    tier = payment.tier

                    # Update or create subscription
                    Subscription.objects.update_or_create(
                        user=request.user,
                        defaults={
                            "tier": tier,
                            "subscribed_at": timezone.now(),
                            "expires_at": timezone.now() + timedelta(days=30),
                        },
                    )

                    # Keep user model in sync
                    request.user.tier = tier
                    request.user.save(update_fields=["tier"])

                    return Response({
                        "status": "success",
                        "tier": tier.name,
                        "amount": payment.amount
                    })
                
            Payment.objects.filter(stripe_session_id=session_id).update(status='failed')
            return Response({"status": "failed"}, status=400)
        except Exception:
            return Response({"error": "Invalid session"}, status=400)
        
class PaymentView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    pagination_class = CustomOffsetPagination
    
    def get(self, request):
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')
        
        page = self.paginate_queryset(payments)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)
    

class ManageSubAccountsView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]
    serializer_class = ManageSubAccountSerializer
    pagination_class = CustomOffsetPagination
    module_name = "accounts"

    def get_queryset(self):
        user = self.request.user
        if user.is_subaccount:
            return User.objects.filter(parent=user.parent)
        return User.objects.filter(parent=user)

    def get(self, request, pk=None):
        queryset = self.get_queryset().prefetch_related('permissions__module')
        if pk:
            try:
                subaccount = queryset.get(pk=pk)
            except User.DoesNotExist:
                return Response({"detail": "Subaccount not found."}, status=404)

            serializer = self.get_serializer(subaccount)
            return Response(serializer.data)
        
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    def put(self, request, pk=None):
        try:
            subaccount = self.get_queryset().get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Subaccount not found."}, status=404)

        serializer = self.get_serializer(subaccount, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DeleteSubAccountView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]
    module_name = "accounts"

    def delete(self, request, pk):
        try:
            subaccount = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Subaccount not found."}, status=404)

        subaccount.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class SubaccountActivationView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOwnerOrHasPermission]
    module_name = "accounts"

    def post(self, request, pk):
        try:
            subaccount = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Subaccount not found."}, status=404)
        
        option = request.data.get("option", "deactivate")
        if option not in ["deactivate", "activate"]:
            return Response({"detail": "Invalid option. Use 'deactivate' or 'activate'."}, status=400)
        
        if option == "activate":
            subaccount.is_active = True
            subaccount.save(update_fields=["is_active"])
            return Response({"detail": "Subaccount activated."}, status=200)
        
        subaccount.is_active = False
        subaccount.save(update_fields=["is_active"])
        return Response({"detail": "Subaccount deactivated."}, status=200)