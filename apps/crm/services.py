from django.urls import reverse
from django.utils import timezone


def send_quote_email(quote, request=None):
    """إرسال عرض السعر بالبريد الإلكتروني للعميل."""
    from apps.campaigns.emailjs_service import send_via_emailjs
    from apps.payments.models import CompanySettings

    email = ''
    name = ''
    if quote.contact and quote.contact.email:
        email = quote.contact.email
        name = quote.contact.full_name
    elif quote.company:
        name = quote.company.name

    if not email:
        return False, 'لا يوجد بريد إلكتروني للعميل'

    c = CompanySettings.load()
    base = request.build_absolute_uri('/').rstrip('/') if request else 'http://165.232.167.39:8000'
    quote_url = base + f'/crm/quotes/{quote.pk}/'

    # بناء HTML العرض
    items_html = ''
    for i, item in enumerate(quote.items.all(), 1):
        items_html += f'''
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eef2f7">{i}</td>
          <td style="padding:10px;border-bottom:1px solid #eef2f7">{item.description}</td>
          <td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:center">{item.quantity}</td>
          <td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left">{item.unit_price}</td>
          <td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left;font-weight:bold">{item.line_total} {quote.currency}</td>
        </tr>'''

    html = f'''
    <div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;background:#f6f8fb;padding:24px">
      <div style="max-width:680px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden">
        <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
          <h1 style="margin:0;font-size:22px">{c.name_ar}</h1>
          <p style="margin:8px 0 0;opacity:.85">عرض سعر</p>
        </div>
        <div style="padding:24px;color:#1f2937;line-height:1.9">
          <h2 style="color:#0b4ea2">مرحباً {name}</h2>
          <p>نتشرف بتقديم عرض السعر التالي لكم، ونأمل أن يلبي احتياجاتكم.</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr style="background:#0b4ea2;color:#fff">
              <th style="padding:10px">#</th>
              <th style="padding:10px">البيان</th>
              <th style="padding:10px">الكمية</th>
              <th style="padding:10px;text-align:left">السعر</th>
              <th style="padding:10px;text-align:left">الإجمالي</th>
            </tr>
            {items_html}
          </table>
          <div style="text-align:left;margin-top:16px">
            <p style="margin:4px 0">الفرعي: <b>{quote.subtotal} {quote.currency}</b></p>
            <p style="margin:4px 0">الضريبة ({quote.tax_rate}%): <b>{quote.tax_amount} {quote.currency}</b></p>
            <p style="font-size:20px;font-weight:bold;color:#0b4ea2;margin-top:8px">الإجمالي: {quote.total} {quote.currency}</p>
          </div>
          {f'<p style="color:#64748b;margin-top:12px">صالح حتى: <b>{quote.valid_until}</b></p>' if quote.valid_until else ''}
          {f'<p style="color:#64748b">{quote.notes}</p>' if quote.notes else ''}
          <p style="text-align:center;margin-top:24px">
            <a href="{quote_url}" style="background:#0b4ea2;color:white;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block">عرض التفاصيل</a>
          </p>
        </div>
        <div style="background:#0b4ea2;color:#fff;text-align:center;padding:14px;font-size:12px">
          {c.name_ar} &nbsp;•&nbsp; {c.website} &nbsp;•&nbsp; {c.phone}
        </div>
      </div>
    </div>'''

    result = send_via_emailjs(
        to_email=email,
        to_name=name,
        subject=f'عرض سعر من {c.name_ar} - {quote.quote_number}',
        body_html=html,
        body_text=f'عرض سعر {quote.quote_number} - الإجمالي: {quote.total} {quote.currency}',
    )

    if result.get('success'):
        quote.status = 'sent'
        quote.save(update_fields=['status'])
        return True, 'تم إرسال العرض بنجاح'
    return False, result.get('error', 'فشل الإرسال')
