
from django.urls import path, include
from . import views as vw
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('account-tier', vw.TierViewSet, basename='account-tier')


urlpatterns = [
    path('register/', vw.RegisterUserView.as_view(), name="register"),
    path('verify_email/', vw.VerifyUserEmail.as_view(), name='verify_email'),
    path('login/', vw.LoginUserView.as_view(), name='login'),
    path('password_reset/', vw.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset_confirm/<uidb64>/<token>/', vw.PasswordResetConfirm.as_view(), name='password_reset_confirm'),
    path('set_new_password/', vw.SetNewPassword.as_view(), name='set_new_password'),
    path('logout/', vw.LogoutUserView.as_view(), name='logout'),
    path('upload_user_profile_image/<int:userid>/', vw.upload_user_profile_image, name='upload_user_profile_image'),
    path('get_uploaded_user_profile_image/<int:userid>/', vw.get_uploaded_user_profile_image, name='get_uploaded_user_profile_image'),
    path('send-otp/', vw.SendOTP.as_view(), name='send_otp'),
    path('create-subaccount/', vw.RegisterSubaccountView.as_view(), name="create-subaccount"),
    
    path('tier-subscription/', vw.SubscriptionView.as_view(), name='tier-subsciption'),
    path('stripe-webhook/', vw.stripe_webhook, name='stripe-webhook'),
    path('verify-checkout/<str:session_id>/', vw.VerifyCheckoutSessionView.as_view(), name='verify-checkout'),
    path('payment-history/', vw.PaymentView.as_view(), name='payment-history'),
    
    path("", include(router.urls))
]
