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

def clean_string(value):
    if not value:
        return ""
    return str(value).replace("\xa0", " ").strip()
    

@shared_task(queue='default')
def send_code_to_user(email):
    try:
        subject = clean_string("One time passcode for Email Verification")
        otp_code =  generate_otp()
        user = User.objects.get(email=email)
        from_email = clean_string(settings.DEFAULT_FROM_EMAIL)
        OneTimePassword.objects.update_or_create(
            user=user,
            defaults={'code': otp_code}
        )
        
        first_name = clean_string(user.first_name)
        last_name = clean_string(user.last_name)
        otp_code = clean_string(generate_otp())

        context = {
            'first_name': first_name,
            'last_name': last_name,
            'otp_code': otp_code
        }

        html_message = render_to_string('verify_email.html', context=context)
        plain_message = strip_tags(html_message)
        
        html_message = html_message.replace("\xa0", " ")
        plain_message = strip_tags(html_message).replace("\xa0", " ")


        d_email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email,
            to=[email],
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )

        d_email.attach_alternative(html_message, 'text/html; charset=utf-8')
        d_email.encoding = "utf-8"
        d_email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Error sending OTP email to {email}: {e}")

@shared_task(queue='default')
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
        email.encoding = "utf-8"
        email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Error sending email to {data['to_email']}: {e}")