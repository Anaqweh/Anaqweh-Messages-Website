from django.urls import reverse
from django.utils import timezone


def send_invoice_email(invoice):
    from apps.campaigns.emailjs_service import send_via_emailjs

    payment = invoice.payment
    if not payment.customer_email:
        return False

    base = 'http://165.232.167.39:8000'
    public_url = base + reverse('payments:invoice_public', args=[invoice.token])
    open_url = base + reverse('payments:invoice_open', args=[invoice.token])

    html = f'''
    <div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;background:#f6f8fb;padding:24px">
      <div style="max-width:680px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden">
        <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
          <h1 style="margin:0">شركة التميز الابتكاري</h1>
          <p style="margin:8px 0 0">فاتورة الدفع الإلكتروني</p>
        </div>
        <div style="padding:24px;color:#1f2937;line-height:1.9">
          <h2>شكراً لدفعك</h2>
          <p>تم استلام دفعتك بنجاح.</p>
          <p><b>رقم الفاتورة:</b> {invoice.invoice_number}</p>
          <p><b>المبلغ:</b> {payment.amount} {payment.currency.upper()}</p>
          <p style="text-align:center;margin-top:22px">
            <a href="{public_url}" style="background:#0b4ea2;color:white;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:bold">عرض الفاتورة</a>
          </p>
          <img src="{open_url}" width="1" height="1" style="display:none" alt="">
        </div>
      </div>
    </div>
    '''

    result = send_via_emailjs(
        to_email=payment.customer_email,
        to_name=payment.customer_name or payment.customer_email,
        subject=f'فاتورتك من INEXC - شركة التميز الابتكاري - {invoice.invoice_number}',
        body_html=html,
        body_text=f'فاتورتك {invoice.invoice_number}: {public_url}',
    )

    if result.get('success'):
        invoice.email_sent_at = timezone.now()
        invoice.save(update_fields=['email_sent_at'])
        return True
    return False


# === Immediate Stripe payment finalizer ===
def finalize_stripe_checkout_payment(session_id, send_email=True):
    from decimal import Decimal
    from django.conf import settings
    from django.utils import timezone
    import stripe
    from .models import Payment, Invoice

    def gv(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def plain(obj):
        if obj is None:
            return {}
        if hasattr(obj, 'to_dict_recursive'):
            return obj.to_dict_recursive()
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if isinstance(obj, dict):
            return {k: plain(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [plain(v) for v in obj]
        return obj

    def cents(value):
        try:
            return Decimal(value or 0) / Decimal('100')
        except Exception:
            return Decimal('0')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.checkout.Session.retrieve(session_id, expand=['payment_intent'])
    payment = Payment.objects.filter(stripe_checkout_session_id=session_id).first()

    if not payment:
        payment = Payment.objects.create(
            source='stripe_success_import',
            description='Stripe Checkout',
            amount=cents(gv(session, 'amount_total', 0)),
            currency=(gv(session, 'currency', None) or getattr(settings, 'STRIPE_CURRENCY', 'aed')).lower(),
            status='pending',
            stripe_checkout_session_id=session_id,
            raw_data=plain(session),
        )

    if gv(session, 'payment_status', '') != 'paid':
        return {'success': False, 'status': gv(session, 'payment_status', ''), 'payment_id': payment.id, 'invoice_sent': False}

    customer = gv(session, 'customer_details', {}) or {}
    payment.customer_email = gv(customer, 'email', '') or payment.customer_email
    payment.customer_name = gv(customer, 'name', '') or payment.customer_name
    payment.status = 'paid'
    payment.paid_at = payment.paid_at or timezone.now()
    payment.raw_data = plain(session)

    pi = gv(session, 'payment_intent', None)
    pi_id = gv(pi, 'id', pi if isinstance(pi, str) else '')
    if pi_id:
        payment.stripe_payment_intent_id = pi_id
        try:
            charges = stripe.Charge.list(payment_intent=pi_id, limit=1, expand=['data.balance_transaction'])
            data = gv(charges, 'data', []) or []
            if data:
                charge = data[0]
                payment.stripe_charge_id = gv(charge, 'id', '') or ''
                bt = gv(charge, 'balance_transaction', None)
                payment.stripe_balance_transaction_id = gv(bt, 'id', bt if isinstance(bt, str) else '') or ''
                if bt and not isinstance(bt, str):
                    payment.stripe_fee = cents(gv(bt, 'fee', 0))
                    payment.net_amount = cents(gv(bt, 'net', 0))
        except Exception:
            pass

    if not payment.net_amount:
        payment.net_amount = payment.amount - payment.stripe_fee

    payment.save()

    invoice, created = Invoice.objects.get_or_create(payment=payment)

    invoice_sent = False
    if send_email and payment.customer_email and not invoice.email_sent_at:
        invoice_sent = bool(send_invoice_email(invoice))

    return {
        'success': True,
        'payment_id': payment.id,
        'invoice_id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'customer_email': payment.customer_email,
        'invoice_sent': invoice_sent,
    }

