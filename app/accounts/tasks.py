import pyotp
from .models import User, OneTimePassword
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

def generate_otp():
    totp = pyotp.TOTP('base32secret3232')
    val = totp.now() # => '492039'
    return val

@shared_task
def send_code_to_user(email):
    try:
        subject = "One time passcode for Email Verification"
        otp_code =  generate_otp()
        user = User.objects.get(email=email)
        from_email = settings.DEFAULT_FROM_EMAIL
        OneTimePassword.objects.update_or_create(
            user=user,
            defaults={'code': otp_code}
        )

        context = {
            'first_name':user.first_name,
            'last_name':user.last_name,
            'otp_code':otp_code
        }

        html_message = render_to_string('verify_email.html', context=context)
        plain_message = strip_tags(html_message)


        d_email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email,
            to=[email]
        )

        d_email.attach_alternative(html_message, 'text/html')
        d_email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Error sending OTP email to {email}: {e}")

@shared_task
def send_normal_email(data, file='reset_password.html'):
    try:
        html_message = render_to_string(file, context=data)
        plain_message = strip_tags(html_message) 


        email = EmailMultiAlternatives(
            subject= data['email_subject'],
            body = plain_message,
            from_email = settings.EMAIL_HOST_USER,
            to = [data['to_email']] 
        )
        email.attach_alternative(html_message, 'text/html')
        email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Error sending email to {data['to_email']}: {e}")