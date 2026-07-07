from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def login_view(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for_user(request.user))

    if request.method == "POST":
        username_value = (request.POST.get("username") or request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        auth_user = authenticate(request, username=username_value, password=password)

        if auth_user is None and "@" in username_value:
            User = get_user_model()
            candidate = User.objects.filter(email__iexact=username_value).first()
            if candidate:
                username_field = getattr(User, "USERNAME_FIELD", "username")
                login_value = getattr(candidate, username_field)
                auth_user = authenticate(request, username=login_value, password=password)

        if auth_user is not None:
            from apps.platform_core.models import AdminTOTP
            totp_rec = AdminTOTP.objects.filter(user=auth_user, is_enabled=True).first()
            if auth_user.is_superuser and totp_rec:
                request.session["pending_2fa_user_id"] = auth_user.id
                request.session["pending_2fa_next"] = request.GET.get("next") or request.POST.get("next") or ""
                return redirect("accounts:verify_2fa")
            auth_login(request, auth_user)
            next_url = request.GET.get("next") or request.POST.get("next")
            return redirect(next_url or dashboard_url_for_user(auth_user))

        return render(request, "accounts/login.html", {
            "error": "بيانات الدخول غير صحيحة.",
            "username": username_value,
        })

    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def profile_view(request):
    return render(request, 'accounts/profile.html')


from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test

User = get_user_model()

def is_superuser(u):
    return u.is_superuser

@user_passes_test(is_superuser)
def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})

@user_passes_test(is_superuser)
def user_create(request):
    if request.method == 'POST':
        username  = request.POST.get('username','').strip()
        password  = request.POST.get('password','').strip()
        email     = request.POST.get('email','').strip()
        full_name = request.POST.get('full_name','').strip()
        role      = request.POST.get('role','staff')
        service_id  = request.POST.get('service_id','').strip()
        template_id = request.POST.get('template_id','').strip()
        public_key  = request.POST.get('public_key','').strip()
        private_key = request.POST.get('private_key','').strip()

        if username and password:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'اسم المستخدم موجود مسبقاً.')
            else:
                names = full_name.split(' ', 1)
                u = User.objects.create_user(username=username, password=password, email=email)
                u.first_name = names[0]
                u.last_name  = names[1] if len(names) > 1 else ''
                u.is_staff = True
                # superuser فقط للمدير العام — لا يُمنح لمستخدمي الشركات
                u.is_superuser = (role == 'admin')
                u.save()
                # حفظ إعدادات EmailJS إذا وُجدت
                from apps.accounts.models import UserEmailJSConfig, UserProfile
                cfg, _ = UserEmailJSConfig.objects.get_or_create(user=u)
                cfg.service_id  = service_id
                cfg.template_id = template_id
                cfg.public_key  = public_key
                cfg.private_key = private_key
                cfg.from_email  = email
                cfg.from_name   = full_name or username
                cfg.is_configured = all([service_id, template_id, public_key, private_key])
                cfg.save()
                messages.success(request, f'تم إنشاء المستخدم {username}.')
                return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html')

@user_passes_test(is_superuser)
def user_delete(request, pk):
    u = User.objects.filter(pk=pk).first()
    if u and not u.is_superuser:
        u.delete()
        messages.success(request, 'تم حذف المستخدم.')
    else:
        messages.error(request, 'لا يمكن حذف مدير.')
    return redirect('accounts:user_list')


from apps.accounts.audit import AuditLog

@user_passes_test(is_superuser)
def audit_log_view(request):
    logs = AuditLog.objects.all()[:300]
    return render(request, 'accounts/audit_log.html', {'logs': logs})


from apps.accounts.models import UserEmailJSConfig, UserProfile
from apps.platform_core.navigation import dashboard_url_for_user


@login_required
def emailjs_settings(request):
    cfg, _ = UserEmailJSConfig.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        cfg.service_id    = request.POST.get('service_id', '').strip()
        cfg.template_id   = request.POST.get('template_id', '').strip()
        cfg.public_key    = request.POST.get('public_key', '').strip()
        cfg.private_key   = request.POST.get('private_key', '').strip()
        cfg.from_email    = request.POST.get('from_email', '').strip()
        cfg.from_name     = request.POST.get('from_name', '').strip()
        cfg.is_configured = all([cfg.service_id, cfg.template_id, cfg.public_key, cfg.private_key])
        cfg.save()
        from apps.accounts.audit import log_action
        log_action(request.user, 'update_emailjs_config', cfg.pk)
        messages.success(request, 'تم حفظ إعدادات EmailJS بنجاح')
        return redirect('accounts:emailjs_settings')
    return render(request, 'accounts/emailjs_settings.html', {'cfg': cfg})


@login_required
def emailjs_test(request):
    if request.method == 'POST':
        from apps.campaigns.emailjs_service import send_via_emailjs
        result = send_via_emailjs(
            to_email=request.user.email,
            to_name=request.user.get_full_name() or request.user.username,
            subject='اختبار إعدادات EmailJS',
            body_html='<h2>مرحباً!</h2><p>إعدادات EmailJS تعمل بشكل صحيح</p>',
            body_text='إعدادات EmailJS تعمل بشكل صحيح',
            user=request.user,
        )
        if result['success']:
            messages.success(request, 'تم الإرسال بنجاح! تحقق من بريدك.')
        else:
            messages.error(request, f'فشل الإرسال: {result["error"]}')
    return redirect('accounts:emailjs_settings')


# ============================================================
# إدارة المستخدمين المتقدمة
# ============================================================

@user_passes_test(is_superuser)
def user_edit(request, pk):
    """تعديل بيانات مستخدم"""
    from apps.accounts.models import UserEmailJSConfig, UserProfile
    u = User.objects.filter(pk=pk).first()
    if not u:
        messages.error(request, 'المستخدم غير موجود')
        return redirect('accounts:user_list')
    cfg, _ = UserEmailJSConfig.objects.get_or_create(user=u)

    if request.method == 'POST':
        u.email      = request.POST.get('email', '').strip()
        u.first_name = request.POST.get('first_name', '').strip()
        u.last_name  = request.POST.get('last_name', '').strip()
        # منع رفع مدير شركة لـ superuser (ثغرة أمنية)
        from apps.platform_core.models import TenantMembership
        user_has_tenant = TenantMembership.objects.filter(user=u).exists()
        if not user_has_tenant:
            u.is_superuser = request.POST.get('role') == 'admin'
        else:
            u.is_superuser = False  # مدير الشركة لا يصبح superuser أبداً
        u.is_active  = request.POST.get('is_active') == '1'
        note         = request.POST.get('note', '').strip()
        max_sends    = request.POST.get('max_sends', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            u.set_password(new_password)
        u.save()
        # EmailJS
        cfg.service_id  = request.POST.get('service_id', '').strip()
        cfg.template_id = request.POST.get('template_id', '').strip()
        cfg.public_key  = request.POST.get('public_key', '').strip()
        cfg.private_key = request.POST.get('private_key', '').strip()
        cfg.api_keys = request.POST.get('api_keys', '').strip()
        cfg.from_email  = request.POST.get('from_email', u.email).strip()
        cfg.from_name   = request.POST.get('from_name', '').strip()
        cfg.is_configured = all([cfg.service_id, cfg.template_id, cfg.public_key, cfg.private_key])
        cfg.save()
        # حفظ الملاحظة والحد
        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.note      = note
        if max_sends.isdigit():
            profile.max_sends = int(max_sends)
        profile.save()
        messages.success(request, f'تم تحديث بيانات {u.username}')
        return redirect('accounts:user_list')

    profile, _ = UserProfile.objects.get_or_create(user=u)
    from apps.platform_core.models import TenantMembership
    user_has_tenant = TenantMembership.objects.filter(user=u).exists()
    return render(request, 'accounts/user_edit.html', {'u': u, 'cfg': cfg, 'profile': profile, 'user_has_tenant': user_has_tenant})


@user_passes_test(is_superuser)
def user_toggle(request, pk):
    """تفعيل/تعطيل مستخدم"""
    u = User.objects.filter(pk=pk).first()
    if u and not u.is_superuser:
        u.is_active = not u.is_active
        u.save()
        status = 'مُفعَّل' if u.is_active else 'مُعطَّل'
        messages.success(request, f'تم {status} حساب {u.username}')
    return redirect('accounts:user_list')


@user_passes_test(is_superuser)
def user_reset_password(request, pk):
    """إعادة تعيين كلمة المرور"""
    u = User.objects.filter(pk=pk).first()
    if request.method == 'POST' and u:
        new_pass = request.POST.get('new_password', '').strip()
        if new_pass:
            u.set_password(new_pass)
            u.save()
            messages.success(request, f'تم تغيير كلمة مرور {u.username}')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_reset_password.html', {'u': u})


@user_passes_test(is_superuser)
def user_detail(request, pk):
    """عرض تفاصيل وإحصائيات مستخدم"""
    from apps.campaigns.models import Campaign, EmailLog
    from apps.accounts.models import UserEmailJSConfig, UserProfile
    u = User.objects.filter(pk=pk).first()
    if not u:
        return redirect('accounts:user_list')
    cfg = getattr(u, 'emailjs_config', None)
    profile, _ = UserProfile.objects.get_or_create(user=u)
    campaigns   = Campaign.objects.filter(owner=u).order_by('-created_at')[:10]
    total_sent  = EmailLog.objects.filter(campaign__owner=u).count()
    total_ok    = EmailLog.objects.filter(campaign__owner=u, status='sent').count()
    audit_logs  = AuditLog.objects.filter(user=u).order_by('-created_at')[:20]
    return render(request, 'accounts/user_detail.html', {
        'u': u, 'cfg': cfg, 'profile': profile,
        'campaigns': campaigns,
        'total_sent': total_sent,
        'total_ok': total_ok,
        'success_rate': round(total_ok/total_sent*100) if total_sent else 0,
        'audit_logs': audit_logs,
    })


# ============ نسيت كلمة المرور ============

def forgot_password(request):
    from django.contrib.auth import get_user_model
    from .models import PasswordResetCode
    from apps.campaigns.emailjs_service import send_via_emailjs
    import random
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            code = str(random.randint(100000, 999999))
            PasswordResetCode.objects.create(user=user, code=code)
            send_via_emailjs(
                to_email=email,
                to_name=user.get_full_name() or user.username,
                subject='رمز إعادة تعيين كلمة المرور - INEXC',
                body_html=f'''
                <div dir="rtl" style="font-family:Arial;background:#f6f8fb;padding:24px">
                <div style="max-width:480px;margin:auto;background:#fff;border-radius:16px;overflow:hidden">
                <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
                <h1 style="margin:0;font-size:22px">INEXC</h1>
                <p style="margin:8px 0 0">إعادة تعيين كلمة المرور</p>
                </div>
                <div style="padding:24px;text-align:center">
                <p>رمز التحقق الخاص بك:</p>
                <div style="font-size:42px;font-weight:800;color:#0b4ea2;letter-spacing:8px;margin:16px 0">{code}</div>
                <p style="color:#64748b;font-size:13px">الرمز صالح لمدة 15 دقيقة فقط</p>
                </div>
                </div>
                </div>''',
                body_text=f'رمز التحقق: {code}',
            )
        from django.contrib import messages as msg
        msg.success(request, 'إذا كان البريد مسجلاً، سيصلك رمز التحقق')
        return redirect('accounts:verify_reset_code')
    return render(request, 'accounts/forgot_password.html')


def verify_reset_code(request):
    from .models import PasswordResetCode
    from django.contrib.auth import get_user_model
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        reset = PasswordResetCode.objects.filter(code=code, is_used=False).order_by('-created_at').first()
        if reset and reset.is_valid():
            request.session['reset_user_id'] = reset.user.id
            request.session['reset_code'] = code
            return redirect('accounts:reset_password')
        from django.contrib import messages as msg
        msg.error(request, 'الرمز غير صحيح أو منتهي الصلاحية')
    return render(request, 'accounts/verify_code.html')


def reset_password(request):
    from .models import PasswordResetCode
    from django.contrib.auth import get_user_model
    user_id = request.session.get('reset_user_id')
    code = request.session.get('reset_code')
    if not user_id or not code:
        return redirect('accounts:forgot_password')
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()
        if len(new_password) < 6:
            from django.contrib import messages as msg
            msg.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        elif new_password != confirm:
            from django.contrib import messages as msg
            msg.error(request, 'كلمتا المرور غير متطابقتين')
        else:
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            user.set_password(new_password)
            user.save()
            PasswordResetCode.objects.filter(code=code).update(is_used=True)
            del request.session['reset_user_id']
            del request.session['reset_code']
            from django.contrib import messages as msg
            msg.success(request, 'تم تغيير كلمة المرور بنجاح — يمكنك تسجيل الدخول الآن')
            return redirect('accounts:login')
    return render(request, 'accounts/reset_password.html')


def forgot_username(request):
    from django.contrib.auth import get_user_model
    from apps.campaigns.emailjs_service import send_via_emailjs
    from django.contrib import messages as msg
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            send_via_emailjs(
                to_email=email,
                to_name=user.get_full_name() or user.username,
                subject='اسم المستخدم الخاص بك - INEXC',
                body_html=f"""<div dir="rtl" style="font-family:Arial;background:#f6f8fb;padding:24px">
<div style="max-width:480px;margin:auto;background:#fff;border-radius:16px;overflow:hidden">
<div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
<h1 style="margin:0;font-size:22px">INEXC</h1>
<p style="margin:8px 0 0">اسم المستخدم الخاص بك</p>
</div>
<div style="padding:24px;text-align:center">
<p>اسم المستخدم المرتبط بهذا البريد:</p>
<div style="font-size:32px;font-weight:800;color:#0b4ea2;margin:16px 0;padding:16px;background:#f4f7fb;border-radius:10px">{user.username}</div>
<p style="color:#64748b;font-size:13px">إذا لم تطلب هذا، تجاهل هذا البريد</p>
</div>
</div>
</div>""",
                body_text=f"اسم المستخدم الخاص بك: {user.username}",
            )
        msg.success(request, 'إذا كان البريد مسجلاً، سيصلك اسم المستخدم')
        return redirect('accounts:login')
    return render(request, 'accounts/forgot_username.html')

def verify_2fa_view(request):
    import pyotp
    from apps.platform_core.models import AdminTOTP
    from django.contrib.auth import get_user_model
    uid = request.session.get("pending_2fa_user_id")
    if not uid:
        return redirect("accounts:login")
    User = get_user_model()
    user = User.objects.filter(pk=uid).first()
    if not user:
        return redirect("accounts:login")
    error = None
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        rec = AdminTOTP.objects.filter(user=user, is_enabled=True).first()
        if rec and pyotp.TOTP(rec.secret).verify(code, valid_window=1):
            auth_login(request, user)
            next_url = request.session.pop("pending_2fa_next", "")
            request.session.pop("pending_2fa_user_id", None)
            return redirect(next_url or dashboard_url_for_user(user))
        error = "الرمز غير صحيح، حاول مجدداً."
    return render(request, "accounts/verify_2fa.html", {"error": error})


@login_required
def setup_2fa_view(request):
    import pyotp, qrcode, io, base64
    from apps.platform_core.models import AdminTOTP
    if not request.user.is_superuser:
        return redirect(dashboard_url_for_user(request.user))
    rec, _ = AdminTOTP.objects.get_or_create(user=request.user, defaults={"secret": pyotp.random_base32()})
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        action = request.POST.get("action")
        if action == "disable":
            rec.is_enabled = False
            rec.save()
            messages.success(request, "تم إيقاف التحقق بخطوتين.")
        elif pyotp.TOTP(rec.secret).verify(code, valid_window=1):
            rec.is_enabled = True
            rec.save()
            messages.success(request, "تم تفعيل التحقق بخطوتين بنجاح.")
        else:
            messages.error(request, "الرمز غير صحيح.")
    uri = pyotp.TOTP(rec.secret).provisioning_uri(name=request.user.username, issuer_name="inexcsuite")
    qr_img = qrcode.make(uri)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return render(request, "accounts/setup_2fa.html", {"rec": rec, "qr_b64": qr_b64, "secret": rec.secret})
