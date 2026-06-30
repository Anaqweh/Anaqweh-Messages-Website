from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EmailTemplate


def _company_user_ids(request):
    """يجلب معرّفات كل المستخدمين في نفس شركة المستخدم الحالي."""
    try:
        from apps.platform_core.navigation import active_membership_for
        from apps.platform_core.models import TenantMembership
        m = active_membership_for(request.user)
        if m and m.tenant_id:
            ids = list(TenantMembership.objects.filter(
                tenant_id=m.tenant_id
            ).values_list('user_id', flat=True))
            if request.user.id not in ids:
                ids.append(request.user.id)
            return ids
    except Exception:
        pass
    return [request.user.id]

def _platform_user_ids():
    """معرّفات مستخدمي المنصة (الذين لا ينتمون لأي شركة)."""
    try:
        from apps.platform_core.models import TenantMembership
        from django.contrib.auth import get_user_model
        U = get_user_model()
        member_ids = set(TenantMembership.objects.values_list('user_id', flat=True))
        return list(U.objects.exclude(id__in=member_ids).values_list('id', flat=True))
    except Exception:
        return []

def _owned(qs, request):
    """عزل كامل: المدير العام يرى قوالب المنصة فقط، وكل شركة ترى قوالبها فقط."""
    from apps.platform_core.navigation import active_membership_for
    m = active_membership_for(request.user)
    if m and m.tenant_id:
        return qs.filter(owner_id__in=_company_user_ids(request))
    return qs.filter(owner_id__in=_platform_user_ids())

@login_required
def template_list(request):
    return render(request, 'templates_mgr/template_list.html', {'templates': _owned(EmailTemplate.objects.all(), request)})

@login_required
def template_create(request):
    if request.method == 'POST':
        name = request.POST.get('name','').strip()
        subject = request.POST.get('subject','').strip()
        body_html = request.POST.get('body_html','').strip()
        body_text = request.POST.get('body_text','').strip()
        if not name or not subject or not body_html:
            messages.error(request, 'يرجى ملء جميع الحقول.')
        else:
            t = EmailTemplate.objects.create(owner=request.user, name=name, subject=subject, body_html=body_html, body_text=body_text)
            messages.success(request, f'تم إنشاء القالب "{name}".')
            return redirect('templates_mgr:template_detail', pk=t.pk)
    return render(request, 'templates_mgr/template_form.html', {'supported_vars': EmailTemplate.SUPPORTED_VARS})

@login_required
def template_detail(request, pk):
    t = get_object_or_404(_owned(EmailTemplate.objects.all(), request), pk=pk)
    return render(request, 'templates_mgr/template_detail.html', {'t': t, 'supported_vars': EmailTemplate.SUPPORTED_VARS})

@login_required
def template_edit(request, pk):
    t = get_object_or_404(_owned(EmailTemplate.objects.all(), request), pk=pk)
    if request.method == 'POST':
        t.name = request.POST.get('name','').strip()
        t.subject = request.POST.get('subject','').strip()
        t.body_html = request.POST.get('body_html','').strip()
        t.body_text = request.POST.get('body_text','').strip()
        t.save()
        messages.success(request, 'تم التحديث.')
        return redirect('templates_mgr:template_detail', pk=t.pk)
    return render(request, 'templates_mgr/template_form.html', {'t': t, 'supported_vars': EmailTemplate.SUPPORTED_VARS})

@login_required
def template_delete(request, pk):
    t = get_object_or_404(_owned(EmailTemplate.objects.all(), request), pk=pk)
    t.delete()
    messages.success(request, 'تم الحذف.')
    return redirect('templates_mgr:template_list')


import os, uuid
from django.http import JsonResponse
from django.conf import settings

@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        img = request.FILES['image']
        if img.size > 5*1024*1024:
            return JsonResponse({'success':False,'error':'الحجم أكبر من 5MB'})
        ext = img.name.rsplit('.',1)[-1].lower()
        if ext not in ('jpg','jpeg','png','gif','webp'):
            return JsonResponse({'success':False,'error':'نوع غير مدعوم'})
        fname = f'{uuid.uuid4().hex}.{ext}'
        path = os.path.join(settings.MEDIA_ROOT, 'email_images', fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path,'wb') as f:
            for chunk in img.chunks():
                f.write(chunk)
        url = request.build_absolute_uri(settings.MEDIA_URL + 'email_images/' + fname)
        return JsonResponse({'success':True,'url':url})
    return JsonResponse({'success':False,'error':'لا توجد صورة'})

@login_required
def builder(request):
    if request.method == 'POST':
        name = request.POST.get('name','').strip()
        subject = request.POST.get('subject','').strip()
        body_html = request.POST.get('body_html','').strip()
        if name and subject and body_html:
            t = EmailTemplate.objects.create(owner=request.user, name=name, subject=subject, body_html=body_html, blocks_json=request.POST.get('blocks_json',''))
            messages.success(request, f'تم حفظ القالب "{name}".')
            return redirect('templates_mgr:template_detail', pk=t.pk)
    edit_pk = request.GET.get('edit')
    ctx = {}
    if edit_pk:
        try:
            _tpl = _owned(EmailTemplate.objects.all(), request).get(pk=edit_pk)
            # عزل: المدير العام يرى الكل، غيره فقط قوالب شركته
            _allowed = request.user.is_superuser
            if not _allowed:
                try:
                    from apps.platform_core.navigation import active_membership_for
                    from apps.platform_core.models import TenantMembership
                    _m = active_membership_for(request.user)
                    if _m:
                        _ids = list(TenantMembership.objects.filter(tenant=_m.tenant).values_list("user_id", flat=True))
                        _ids.append(request.user.id)
                        _allowed = _tpl.owner_id in _ids
                    else:
                        _allowed = (_tpl.owner_id == request.user.id)
                except Exception:
                    _allowed = (_tpl.owner_id == request.user.id)
            if _allowed:
                ctx['edit_template'] = _tpl
        except EmailTemplate.DoesNotExist:
            pass
    return render(request, 'templates_mgr/builder.html', ctx)


@login_required
def upload_document(request):
    if request.method == 'POST' and request.FILES.get('document'):
        doc = request.FILES['document']
        if doc.size > 20 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'الحجم أكبر من 20MB'})
        orig = doc.name
        ext = orig.rsplit('.', 1)[-1].lower() if '.' in orig else 'bin'
        fname = f'{uuid.uuid4().hex}.{ext}'
        path = os.path.join(settings.MEDIA_ROOT, 'email_files', fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            for chunk in doc.chunks():
                f.write(chunk)
        url = request.build_absolute_uri(settings.MEDIA_URL + 'email_files/' + fname)
        size_kb = doc.size / 1024
        size_str = f'{size_kb/1024:.1f} MB' if size_kb >= 1024 else f'{size_kb:.0f} KB'
        return JsonResponse({'success': True, 'url': url, 'name': orig, 'ext': ext, 'size': size_str})
    return JsonResponse({'success': False, 'error': 'لا يوجد ملف'})


@login_required
def create_checkout(request):
    """ينشئ Stripe Checkout Session من مبلغ ويعيد رابط الدفع"""
    import stripe
    import json as _json
    from django.urls import reverse
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طريقة غير مسموحة'})
    try:
        data = _json.loads(request.body.decode('utf-8'))
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return JsonResponse({'success': False, 'error': 'المبلغ غير صالح'})
        label = (data.get('label') or 'دفعة').strip()[:120]
        customer_email = (data.get('email') or '').strip()
        customer_name = (data.get('name') or '').strip()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        base = request.build_absolute_uri('/')[:-1]
        from apps.payments.models import Payment
        payment = Payment.objects.create(
            source='email_quick_checkout',
            customer_email=customer_email,
            customer_name=customer_name,
            description=label,
            amount=amount,
            currency=getattr(settings, 'STRIPE_CURRENCY', 'aed'),
            status='pending',
        )
        try:
            from apps.payments.views import _finance_tenant_for_request as _pay_tenant
            _pt = _pay_tenant(request)
            if _pt is not None and hasattr(payment, 'tenant_id'):
                payment.tenant = _pt
                payment.save(update_fields=['tenant'])
        except Exception:
            pass
        session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': settings.STRIPE_CURRENCY,
                    'product_data': {'name': label},
                    'unit_amount': int(round(amount * 100)),
                },
                'quantity': 1,
            }],
            success_url=base + '/templates/pay/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=base + '/templates/pay/cancel/',
            customer_email=customer_email or None,
            metadata={'payment_id': str(payment.id), 'source': 'email_quick_checkout'},
        )
        payment.stripe_checkout_session_id = session.id
        payment.save(update_fields=['stripe_checkout_session_id'])
        return JsonResponse({'success': True, 'url': session.url})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def pay_success(request):
    from django.http import HttpResponse
    return HttpResponse('<div style="font-family:Tahoma,Arial;text-align:center;direction:rtl;padding:60px"><h1 style="color:#10b981">تم الدفع بنجاح ✅</h1><p style="color:#555">شكراً لك. تمت معالجة دفعتك.</p></div>')


def pay_cancel(request):
    from django.http import HttpResponse
    return HttpResponse('<div style="font-family:Tahoma,Arial;text-align:center;direction:rtl;padding:60px"><h1 style="color:#ef4444">تم إلغاء الدفع</h1><p style="color:#555">لم تكتمل العملية. يمكنك المحاولة مرة أخرى.</p></div>')


@login_required
def create_bank_page(request):
    """ينشئ صفحة معلومات بنكية ويعيد رابطها القصير"""
    import json as _json
    from .models import BankPaymentPage
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طريقة غير مسموحة'})
    try:
        d = _json.loads(request.body.decode('utf-8'))
        page = BankPaymentPage.objects.create(
            owner=request.user,
            title=(d.get('title') or 'معلومات الدفع')[:200],
            bank_name=(d.get('bank_name') or '')[:200],
            account_name=(d.get('account_name') or '')[:200],
            iban=(d.get('iban') or '')[:80],
            account_number=(d.get('account_number') or '')[:80],
            swift=(d.get('swift') or '')[:40],
            country=(d.get('country') or '')[:80],
            currency=(d.get('currency') or '')[:20],
            amount=(d.get('amount') or '')[:40],
            notes=(d.get('notes') or ''),
        )
        url = request.build_absolute_uri('/templates/pay/bank/' + page.code + '/')
        return JsonResponse({'success': True, 'url': url, 'code': page.code})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def bank_page(request, code):
    """يعرض صفحة معلومات بنكية أنيقة"""
    from django.http import HttpResponse, Http404
    from django.utils.html import escape
    from .models import BankPaymentPage
    try:
        p = BankPaymentPage.objects.get(code=code)
    except BankPaymentPage.DoesNotExist:
        raise Http404('الصفحة غير موجودة')
    rows = [
        ('اسم البنك', p.bank_name), ('اسم صاحب الحساب', p.account_name),
        ('رقم الآيبان IBAN', p.iban), ('رقم الحساب', p.account_number),
        ('السويفت SWIFT/BIC', p.swift), ('الدولة', p.country),
        ('العملة', p.currency), ('المبلغ', p.amount),
    ]
    items = ''
    for label, val in rows:
        if not val:
            continue
        v = escape(val)
        items += f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid #eef2f7;gap:12px">
<div style="text-align:right"><div style="font-size:12px;color:#94a3b8;margin-bottom:3px">{escape(label)}</div>
<div style="font-weight:bold;color:#1e293b;font-size:15px;direction:ltr;text-align:right">{v}</div></div>
<button onclick="navigator.clipboard.writeText('{v}');this.textContent='تم النسخ ✓';setTimeout(()=>this.textContent='نسخ',1500)" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:6px 12px;cursor:pointer;color:#475569;font-size:12px;white-space:nowrap">نسخ</button></div>'''
    notes = f'<div style="padding:14px 16px;color:#64748b;font-size:14px;line-height:1.7;background:#f8fafc">{escape(p.notes)}</div>' if p.notes else ''
    html = f'''<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(p.title)}</title></head>
<body style="margin:0;background:#f1f5f9;font-family:Tahoma,Arial,sans-serif;padding:20px">
<div style="max-width:480px;margin:30px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
<div style="background:#1e3a8a;color:#fff;padding:24px;text-align:center"><div style="font-size:32px;margin-bottom:6px">🏦</div><h1 style="margin:0;font-size:20px">{escape(p.title)}</h1></div>
{items}{notes}
<div style="padding:16px;text-align:center;color:#94a3b8;font-size:12px">حوّل المبلغ إلى الحساب أعلاه ثم احتفظ بإيصال التحويل</div>
</div></body></html>'''
    return HttpResponse(html)


def pay_start(request):
    """صفحة وسيطة (GET) تنشئ Stripe Checkout وتحوّل المستخدم — تصلح لروابط البريد"""
    import stripe
    from django.http import HttpResponse
    from django.shortcuts import redirect
    try:
        amount = float(request.GET.get('amount', 0))
        label = (request.GET.get('label') or 'دفعة').strip()[:120]
        if amount <= 0:
            return HttpResponse('<div style="font-family:Tahoma;text-align:center;padding:60px;direction:rtl"><h2>مبلغ غير صالح</h2></div>')
        stripe.api_key = settings.STRIPE_SECRET_KEY
        base = request.build_absolute_uri('/')[:-1]
        session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': settings.STRIPE_CURRENCY,
                    'product_data': {'name': label},
                    'unit_amount': int(round(amount * 100)),
                },
                'quantity': 1,
            }],
            success_url=base + '/templates/pay/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=base + '/templates/pay/cancel/',
        customer_email=customer_email or None,
        metadata={'payment_id': str(payment.id), 'source': 'email_quick_checkout'},
        )
        return redirect(session.url)
    except Exception as e:
        return HttpResponse('<div style="font-family:Tahoma;text-align:center;padding:60px;direction:rtl"><h2>تعذّر بدء الدفع</h2><p style="color:#888">' + str(e) + '</p></div>')


def quick_checkout(request):
    """Public email-safe Stripe checkout redirect."""
    import stripe
    from django.conf import settings
    from apps.payments.models import Payment
    from django.http import HttpResponse, HttpResponseRedirect

    try:
        amount = float(request.GET.get('amount', 0))
    except Exception:
        amount = 0

    if amount < 2:
        return HttpResponse('المبلغ يجب أن يكون 2 AED أو أكثر', status=400)

    label = (request.GET.get('label') or 'دفع').strip()[:120]
    stripe.api_key = settings.STRIPE_SECRET_KEY
    base = request.build_absolute_uri('/').rstrip('/')

    customer_email = (request.GET.get('email') or '').strip()
    customer_name = (request.GET.get('name') or '').strip()
    payment = Payment.objects.create(
        source='email_quick_checkout',
        customer_email=customer_email,
        customer_name=customer_name,
        description=label,
        amount=amount,
        currency=getattr(settings, 'STRIPE_CURRENCY', 'aed'),
        status='pending',
    )

    session = stripe.checkout.Session.create(
        mode='payment',
        line_items=[{
            'price_data': {
                'currency': settings.STRIPE_CURRENCY,
                'product_data': {'name': label},
                'unit_amount': int(round(amount * 100)),
            },
            'quantity': 1,
        }],
        success_url=base + '/templates/pay/success/?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=base + '/templates/pay/cancel/',
        customer_email=customer_email or None,
        metadata={'payment_id': str(payment.id), 'source': 'email_quick_checkout'},
    )
    payment.stripe_checkout_session_id = session.id
    payment.save(update_fields=['stripe_checkout_session_id'])
    return HttpResponseRedirect(session.url)



# === FINAL FIX: quick checkout must register Payment before Stripe redirect ===
def quick_checkout(request):
    from decimal import Decimal, InvalidOperation
    from django.conf import settings
    from django.http import HttpResponse, HttpResponseRedirect
    from django.utils import timezone
    import stripe
    from apps.payments.models import Payment

    raw_amount = (request.GET.get('amount') or '2').strip().replace(',', '.')
    try:
        amount = Decimal(raw_amount).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        amount = Decimal('2.00')

    if amount < Decimal('2.00'):
        amount = Decimal('2.00')

    label = (request.GET.get('label') or 'الدفع').strip()[:200]
    currency = getattr(settings, 'STRIPE_CURRENCY', 'aed') or 'aed'

    payment = Payment.objects.create(
        source='email_quick_checkout',
        description=label,
        amount=amount,
        currency=currency.lower(),
        status='pending',
        raw_data={
            'created_from': 'templates_mgr.quick_checkout',
            'created_at': timezone.now().isoformat(),
            'query_amount': raw_amount,
            'query_label': label,
        },
    )

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        base = request.build_absolute_uri('/').rstrip('/')
        session = stripe.checkout.Session.create(
            mode='payment',
            customer_creation='always',
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'product_data': {'name': label},
                    'unit_amount': int(amount * 100),
                },
                'quantity': 1,
            }],
            success_url=base + '/templates/pay/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=base + '/templates/pay/cancel/',
            metadata={
                'payment_id': str(payment.id),
                'source': 'email_quick_checkout',
            },
        )
        payment.stripe_checkout_session_id = session.id
        payment.raw_data = {
            **(payment.raw_data or {}),
            'stripe_checkout_url': session.url,
            'stripe_checkout_session_id': session.id,
        }
        payment.save(update_fields=['stripe_checkout_session_id', 'raw_data', 'updated_at'])
        return HttpResponseRedirect(session.url)
    except Exception as e:
        payment.status = 'failed'
        payment.raw_data = {**(payment.raw_data or {}), 'error': str(e)}
        payment.save(update_fields=['status', 'raw_data', 'updated_at'])
        return HttpResponse('تعذر إنشاء رابط الدفع: ' + str(e), status=500)


# === Immediate invoice on Stripe success redirect ===
def pay_success(request):
    from django.http import HttpResponse
    session_id = request.GET.get('session_id', '').strip()

    if not session_id:
        return HttpResponse('<div dir="rtl" style="font-family:Tahoma;text-align:center;padding:60px"><h1 style="color:#10b981">تم الدفع بنجاح</h1><p>تم استلام العملية. سيتم إرسال الفاتورة تلقائياً بعد المزامنة.</p></div>')

    try:
        from apps.payments.services import finalize_stripe_checkout_payment
        result = finalize_stripe_checkout_payment(session_id, send_email=True)
        if result.get('success'):
            sent_msg = 'وتم إرسال الفاتورة إلى بريدك الإلكتروني.' if result.get('invoice_sent') else 'تم إنشاء الفاتورة، وسيتم إرسالها قريباً.'
            return HttpResponse(f'<div dir="rtl" style="font-family:Tahoma;text-align:center;padding:60px"><h1 style="color:#10b981">تم الدفع بنجاح</h1><p>{sent_msg}</p><p>رقم الفاتورة: <b>{result.get("invoice_number","")}</b></p></div>')
        return HttpResponse('<div dir="rtl" style="font-family:Tahoma;text-align:center;padding:60px"><h1 style="color:#f59e0b">الدفع قيد التحقق</h1><p>لم يؤكد Stripe الدفع بعد. سيتم التحقق تلقائياً.</p></div>')
    except Exception as e:
        return HttpResponse('<div dir="rtl" style="font-family:Tahoma;text-align:center;padding:60px"><h1 style="color:#ef4444">تم الدفع لكن تعذر إرسال الفاتورة فوراً</h1><p>سيتم إرسالها تلقائياً بعد المزامنة.</p><p style="color:#777">' + str(e) + '</p></div>', status=200)


def countdown_image(request):
    """يولّد GIF متحرك للعدّاد التنازلي - يتحرك عند فتح الإيميل (الثواني تنقص بصرياً)."""
    from django.http import HttpResponse
    from datetime import datetime
    from PIL import Image, ImageDraw, ImageFont
    import io

    date_str = request.GET.get('date', '')
    color = request.GET.get('color', 'e4405f')
    if not color.startswith('#'):
        color = '#' + color

    def hex2rgb(h):
        h = h.lstrip('#')
        try:
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return (228, 64, 95)
    box_color = hex2rgb(color)

    try:
        font_num = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 40)
        font_lbl = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    except Exception:
        font_num = ImageFont.load_default()
        font_lbl = ImageFont.load_default()

    box_w, box_h, gap, pad = 90, 90, 12, 20
    label_h = 28
    total_w = box_w * 4 + gap * 3 + pad * 2
    total_h = box_h + label_h + pad * 2

    # الوقت المتبقي الأساسي
    try:
        target = datetime.fromisoformat(date_str.replace('Z', ''))
        base_diff = (target - datetime.now()).total_seconds()
    except Exception:
        base_diff = 0
    if base_diff < 0:
        base_diff = 0

    FRAMES = 60  # 60 إطار = دقيقة من الحركة
    frames = []
    for fr in range(FRAMES):
        diff = base_diff - fr
        if diff < 0:
            diff = 0
        days = int(diff // 86400)
        hours = int((diff % 86400) // 3600)
        mins = int((diff % 3600) // 60)
        secs = int(diff % 60)
        units = [(days, 'Days'), (hours, 'Hours'), (mins, 'Min'), (secs, 'Sec')]

        img = Image.new('RGB', (total_w, total_h), '#ffffff')
        d = ImageDraw.Draw(img)
        x = pad
        for val, lbl in units:
            d.rounded_rectangle([x, pad, x + box_w, pad + box_h], radius=12, fill=box_color)
            txt = f'{val:02d}'
            bb = d.textbbox((0, 0), txt, font=font_num)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            d.text((x + (box_w-tw)/2, pad + (box_h-th)/2 - bb[1]), txt, fill='#ffffff', font=font_num)
            bb2 = d.textbbox((0, 0), lbl, font=font_lbl)
            lw = bb2[2]-bb2[0]
            d.text((x + (box_w-lw)/2, pad + box_h + 4), lbl, fill='#666666', font=font_lbl)
            x += box_w + gap
        frames.append(img)

    buf = io.BytesIO()
    frames[0].save(buf, format='GIF', save_all=True, append_images=frames[1:],
                   duration=1000, loop=1, optimize=True)
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type='image/gif')
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    return resp
