
from rest_framework.generics import GenericAPIView
from .serializers import UserRegisterSerializer, LoginSerializer, PasswordResetSerializer,SetNewPasswordSerializer, LogoutUserSerializer, VerifyEmailSerializer, UploadedUserProfileImageSerializer
from rest_framework.response import Response
from rest_framework import status
from .utils import send_code_to_user
from .models import OneTimePassword, User, UploadedUserProfileImage
from django.utils.encoding import smart_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponseRedirect
from django.shortcuts import render
from rest_framework.decorators import api_view
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from django.http import JsonResponse



class RegisterUserView(GenericAPIView):
    serializer_class = UserRegisterSerializer

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
    def post(self, request):
        email = request.data['email']
        try:
            user = User.objects.get(email=email)
            if not user.is_verified:
                send_code_to_user(email)
                return Response({"message":"code sent to your email"}, status=status.HTTP_200_OK)
            return Response({"message":"user already verified"}, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({"message":"user does not exist"}, status=status.HTTP_404_NOT_FOUND)
            
# class VerifyUserEmail(GenericAPIView):
#     def post(self, request):
#         otpcode = request.data.get('otp')
#         try:
#             user_code_obj = OneTimePassword.objects.get(code = otpcode)
#             user = user_code_obj.user
#             if not user.is_verified:
#                 user.is_verified = True
#                 user.save()
#                 return Response({
#                     "message":"account email verified successfully"
#                 }, status=status.HTTP_200_OK)
#             return Response({
#                 "message":"code is invalid, user already verified."
#             }, status=status.HTTP_204_NO_CONTENT)
#         except OneTimePassword.DoesNotExist:
#             return Response({"message":"Passcode not provided"}, status=status.HTTP_404_NOT_FOUND)
    
class VerifyUserEmail(GenericAPIView):
    serializer_class = VerifyEmailSerializer

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
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context = {'request':request})
        serializer.is_valid(raise_exception=True)
        return Response (serializer.data, status=status.HTTP_200_OK)



class PasswordResetView(GenericAPIView):
    serializer_class = PasswordResetSerializer
    def post(self, request):
        serializer = self.serializer_class(data = request.data, context ={'request':request})
        serializer.is_valid(raise_exception = True)
     
        return Response({'message':"A link has been sent to your email to reset your password"}, status=status.HTTP_200_OK)
    
class PasswordResetConfirm(GenericAPIView):
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


# Function to upload image to cloudinary
@api_view(['POST'])
def upload_user_profile_image(request, userid):

    if request.method == 'POST':
        serializer = UploadedUserProfileImageSerializer(data=request.data)
        if serializer.is_valid():
            # Upload an image
            image_file = request.FILES.get("image_url")
            upload_result = cloudinary.uploader.upload(image_file, public_id=f"profile_{userid}")
            # Optimize delivery by resizing and applying auto-format and auto-quality
            optimize_url, _ = cloudinary_url(f"profile_{userid}", fetch_format="auto", quality="auto")
            # Transform the image: auto-crop to square aspect_ratio
            auto_crop_url, _ = cloudinary_url(f"profile_{userid}", width=500, height=500, crop="auto", gravity="auto")
            try:
                UploadedUserProfileImage.objects.filter(user_id=userid).update(image_url=upload_result["secure_url"])
            except:
                save_image = UploadedUserProfileImage(image_url=upload_result["secure_url"], image_name=upload_result["public_id"], user_id=userid)
                save_image.save()
            return Response({"image_uploaded":upload_result}, status=201)
    return Response(serializer.errors, status=400)


# Get image details
@api_view(['GET'])
def get_uploaded_user_profile_image(request, userid):
    save_image = UploadedUserProfileImage.objects.filter(user_id=userid, image_name=f"profile_{userid}").values()
    return JsonResponse({"profile_image":list(save_image)}, safe=False, status=status.HTTP_200_OK)
 