
from django.urls import path
from .views import RegisterUserView, VerifyUserEmail, LoginUserView, PasswordResetView,PasswordResetConfirm,SetNewPassword, LogoutUserView, upload_user_profile_image, get_uploaded_user_profile_image, SendOTP



urlpatterns = [
    path('register/', RegisterUserView.as_view(), name="register"),
    path('verify_email/', VerifyUserEmail.as_view(), name='verify_email'),
    path('login/', LoginUserView.as_view(), name='login'),
    path('password_reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password_reset_confirm/<uidb64>/<token>/', PasswordResetConfirm.as_view(), name='password_reset_confirm'),
    path('set_new_password/', SetNewPassword.as_view(), name='set_new_password'),
    path('logout/', LogoutUserView.as_view(), name='logout'),
    path('upload_user_profile_image/<int:userid>/', upload_user_profile_image, name='upload_user_profile_image'),
    path('get_uploaded_user_profile_image/<int:userid>/', get_uploaded_user_profile_image, name='get_uploaded_user_profile_image'),
    path('send-otp/', SendOTP.as_view(), name='send_otp'),
]
