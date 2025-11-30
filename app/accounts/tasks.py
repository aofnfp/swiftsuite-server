import pyotp
from .models import User, OneTimePassword
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from celery import shared_task
import logging, json
from datetime import datetime as dt
from O365 import Account, FileSystemTokenBackend

logger = logging.getLogger(__name__)

credentials = (
    settings.O365_CLIENT_ID, 
    settings.O365_CLIENT_SECRET
)

token_backend = FileSystemTokenBackend(
    token_path='.', 
    token_filename='o365_token.txt'
)

account = Account(credentials, token_backend=token_backend)

def get_graph_account():
    """
    Returns an authenticated Microsoft Graph Account.
    Refreshes the token automatically if expired.
    """
    account = Account(
        credentials,
        auth_flow_type='credentials',
        tenant_id=settings.O365_TENANT_ID,
        token_backend=token_backend
    )
    if not account.is_authenticated:
        # For client-credential flow, authenticate() happens automatically.
        account.authenticate()
    return account


def send_graph_email(to, subject, html_body, plain_body):
    """
    Sends email via Microsoft Graph API.
    """
    account = get_graph_account()
    mailbox = account.mailbox(resource=settings.DEFAULT_FROM_EMAIL)

    message = mailbox.new_message()
    message.to.add(to)
    message.subject = subject
    message.body = html_body
    message.body_type = "html"

    message.send()

def generate_otp():
    totp = pyotp.TOTP('base32secret3232')
    val = totp.now() # => '492039'
    return val


@shared_task(queue='default')
def send_code_to_user(email):
    try:
        subject = "One time passcode for Email Verification"
        otp_code =  generate_otp()
        user = User.objects.get(email=email)
        from_email =settings.DEFAULT_FROM_EMAIL
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

        send_graph_email(email, subject, html_message, plain_message)
        
    except Exception as e:
        logger.error(f"Error sending OTP email to {email}: {e}")

@shared_task(queue='default')
def send_normal_email(data, file='reset_password.html'):
    try:
        if data.get('user'):
            user = User.objects.get(id=data['user'])
            data['user'] = user
            data['to_email'] = user.email
        if data.get('vendor'):
            from vendorActivities.models import Vendors
            vendor = Vendors.objects.get(id=data['vendor'])
            data['vendor'] = vendor
        
        data['current_year'] = dt.now().year
        
        
        def clean_text(value):
            if isinstance(value, str):
                return value.replace('\xa0', ' ').encode('utf-8', errors='ignore').decode('utf-8')
            return value

        # Clean all string data
        for key in list(data.keys()):
            data[key] = clean_text(data[key])
            
        logger.debug(f"Email data before sending: {json.dumps(data, default=str, ensure_ascii=False)}")

            
        html_message = render_to_string(file, context=data)
        html_message = clean_text(html_message)
        plain_message = strip_tags(html_message)
 
        send_graph_email(
            data['to_email'], 
            data['subject'], 
            html_message, 
            plain_message
        )
    except Exception as e:
        logger.error(f"Error sending email to {data['to_email']}: {e}", exc_info=True)