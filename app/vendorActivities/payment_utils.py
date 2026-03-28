# vendors/services/payment_service.py
import stripe
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from accounts.models import Payment, Charge

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_vendor_checkout_session(request, vendor):
    """
    Creates a Stripe Checkout session for a vendor force integration.
    Returns the Stripe session object.
    """
    try:
        charge = Charge.objects.filter(key='custom_supplier').first()
        if not charge:
            return Response({'error': 'Charge configuration not found.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        amount = charge.total_amount * 100  # Convert to cents
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"Force Integration - {vendor.name}",
                        'description': "Priority vendor integration service.",
                    },
                    'unit_amount': int(amount),  # amount in cents
                },
                'quantity': 1,
            }],
            mode='payment',
            customer_email=request.user.email,
            success_url='https://swiftsuite.app/vendors/payment-success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://swiftsuite.app/vendors/payment-failed/',
            metadata={
                'user_id': request.user.id,
                'vendor_id': vendor.id,
                'request_type': 'force'
            }
        )
        
        Payment.objects.create(
            user=request.user,
            vendor=vendor,
            amount=charge.total_amount,
            status='pending',
            payment_type='one_time',
            stripe_session_id=checkout_session.id
        )

        
        return checkout_session
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_VENDOR_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        vendor_id = session['metadata'].get('vendor_id')

        Payment.objects.filter(stripe_session_id=session['id']).update(status='paid')

    return HttpResponse(status=200)

