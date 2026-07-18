from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import RegistrationFormTemplate, RegistrationSubmission

try:
    from .forms import RegistrationTemplateForm, DynamicRegistrationSubmissionForm
except Exception:
    RegistrationTemplateForm = None
    DynamicRegistrationSubmissionForm = None


SPARK_GENERAL_ENGLISH = [
    "General English Foundation", "General English Level 1", "General English Level 2",
    "General English Level 3", "General English Level 4", "General English Level 5",
    "General English Level 6", "General English Level 7", "General English Level 8",
    "General English Level 9", "General English Level 10", "General English Level 11",
]

SPARK_OTHER_COURSES = [
    "Go English", "Market Leader", "English for Marketing", "English for Customer Care",
    "English for Business", "Working English", "English for Meetings",
    "English for Presentations", "Other Languages", "TOEFL", "IELTS", "ALCPT", "PTE",
]

SPARK_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
SPARK_PAYMENT_METHODS = ["Bank Transfer", "Visa", "Cheque", "Cash"]
SPARK_DURATIONS = ["2 Months", "4 Months", "6 Months", "8 Months", "10 Months", "12 Months"]


def _model_fields(model):
    return {field.name for field in model._meta.fields}


def _reg_user_tenant(request):
    """يرجع شركة (tenant) المستخدم الحالي، أو None للمدير العام."""
    if request.user.is_superuser:
        return None
    from apps.platform_core.navigation import active_membership_for
    membership = active_membership_for(request.user)
    return membership.tenant if membership else None

def _template_qs(request):
    qs = RegistrationFormTemplate.objects.all()
    _t = _reg_user_tenant(request)
    if _t is not None:
        qs = qs.filter(tenant=_t)
    return qs


def _submission_qs(request):
    qs = RegistrationSubmission.objects.select_related("template").all()
    _t = _reg_user_tenant(request)
    if _t is not None:
        qs = qs.filter(tenant=_t)
    return qs



SPARK_DEFAULT_REGISTRATION_TYPES = [
    {"value": "New Student", "ar": "طالب جديد", "en": "New Student"},
    {"value": "Re-enroll", "ar": "تجديد داخل المعهد", "en": "Re-enroll"},
    {"value": "Online", "ar": "عن بعد", "en": "Online"},
    {"value": "One to one (VIP)", "ar": "One to one (VIP)", "en": "One to one (VIP)"},
]


def _spark_registration_types(template_obj):
    schema = getattr(template_obj, "schema", None) or {}
    options = schema.get("registration_types") or schema.get("registration_type_options") or SPARK_DEFAULT_REGISTRATION_TYPES

    normalized = []
    for item in options:
        if isinstance(item, dict):
            value = item.get("value") or item.get("en") or item.get("label") or ""
            normalized.append({
                "value": value,
                "ar": item.get("ar") or item.get("label_ar") or value,
                "en": item.get("en") or item.get("label_en") or value,
            })
        elif item:
            normalized.append({"value": str(item), "ar": str(item), "en": str(item)})

    return normalized or SPARK_DEFAULT_REGISTRATION_TYPES


def _spark_context(template_obj, posted=None):
    return {
        "template_obj": template_obj,
        "posted": posted or {},
        "general_english_courses": SPARK_GENERAL_ENGLISH,
        "other_courses": SPARK_OTHER_COURSES,
        "days": SPARK_DAYS,
        "payment_methods": SPARK_PAYMENT_METHODS,
        "durations": SPARK_DURATIONS,
        "registration_types": _spark_registration_types(template_obj),
    }


@login_required
def dashboard(request):
    templates = _template_qs(request).order_by("-id")
    submissions = _submission_qs(request).order_by("-id")[:30]
    return render(request, "registrations/dashboard.html", {
        "templates": templates,
        "submissions": submissions,
    })


@login_required
def template_create(request):
    if RegistrationTemplateForm is None:
        return HttpResponse("RegistrationTemplateForm is missing", status=500)

    if request.method == "POST":
        form = RegistrationTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            if hasattr(obj, "created_by_id"):
                obj.created_by = request.user
            _user_tenant = _reg_user_tenant(request)
            if hasattr(obj, "tenant") and _user_tenant is not None:
                obj.tenant = _user_tenant
            obj.save()
            messages.success(request, "تم حفظ النموذج")
            return redirect("registrations:dashboard")
    else:
        form = RegistrationTemplateForm()

    return render(request, "registrations/template_form.html", {"form": form})


@login_required
def template_edit(request, pk):
    template_obj = get_object_or_404(_template_qs(request), pk=pk)

    if RegistrationTemplateForm is None:
        return HttpResponse("RegistrationTemplateForm is missing", status=500)

    if request.method == "POST":
        form = RegistrationTemplateForm(request.POST, request.FILES, instance=template_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ التعديلات")
            return redirect("registrations:dashboard")
    else:
        form = RegistrationTemplateForm(instance=template_obj)

    return render(request, "registrations/template_form.html", {
        "form": form,
        "template_obj": template_obj,
    })


@login_required
def fill_form(request, pk):
    template_obj = get_object_or_404(_template_qs(request).filter(is_active=True), pk=pk)
    return render(request, "registrations/fill_form.html", {
        "template_obj": template_obj,
    })


@login_required
def spark_fill_form(request, pk):
    template_obj = get_object_or_404(_template_qs(request).filter(is_active=True), pk=pk)

    if request.method == "POST":
        data = {}
        for key in request.POST.keys():
            if key == "csrfmiddlewaretoken":
                continue
            values = request.POST.getlist(key)
            data[key] = values if len(values) > 1 else (values[0] if values else "")

        required = {
            "full_name": "Full name",
            "mobile": "Mobile Number",
            "email": "Email",
        }
        missing = [label for key, label in required.items() if not str(data.get(key, "")).strip()]
        if missing:
            messages.error(request, "يرجى تعبئة الحقول المطلوبة: " + "، ".join(missing))
            return render(request, "registrations/spark_fill_form.html", _spark_context(template_obj, data))

        fields = _model_fields(RegistrationSubmission)
        kwargs = {
            "template": template_obj,
            "data": data,
        }

        if "student_name" in fields:
            kwargs["student_name"] = data.get("full_name", "")
        if "student_email" in fields:
            kwargs["student_email"] = data.get("email", "")
        if "signature_data" in fields:
            kwargs["signature_data"] = data.get("signature_data", "")
        if "status" in fields:
            kwargs["status"] = "submitted"
        if "created_by" in fields:
            kwargs["created_by"] = request.user
        if "tenant" in fields:
            kwargs["tenant"] = getattr(template_obj, "tenant", None)

        submission = RegistrationSubmission.objects.create(**kwargs)
        return redirect("registrations:submission_detail", pk=submission.pk)

    return render(request, "registrations/spark_fill_form.html", _spark_context(template_obj))


@login_required
def submission_detail(request, pk):
    submission = get_object_or_404(_submission_qs(request), pk=pk)
    return render(request, "registrations/submission_detail.html", {
        "submission": submission,
        "data": submission.data or {},
        "registration_types": _spark_registration_types(submission.template),
    })


@login_required
def submission_pdf(request, pk):
    submission = get_object_or_404(_submission_qs(request), pk=pk)
    html = render_to_string("registrations/submission_pdf.html", {
        "submission": submission,
        "data": submission.data or {},
    }, request=request)

    from weasyprint import HTML
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="registration-{submission.pk}.pdf"'
    return response


@login_required
def spark_submission_pdf(request, pk):
    submission = get_object_or_404(_submission_qs(request), pk=pk)
    html = render_to_string("registrations/spark_submission_pdf.html", {
        "submission": submission,
        "data": submission.data or {},
    }, request=request)

    from weasyprint import HTML
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="spark-registration-{submission.pk}.pdf"'
    return response


@login_required
def spark_submission_edit(request, pk):
    submission = get_object_or_404(_submission_qs(request), pk=pk)
    template_obj = submission.template
    if request.method == "POST":
        data = dict(submission.data or {})
        for key in request.POST.keys():
            if key == "csrfmiddlewaretoken":
                continue
            values = request.POST.getlist(key)
            data[key] = values if len(values) > 1 else (values[0] if values else "")
        submission.data = data
        if hasattr(submission, "student_name"):
            submission.student_name = data.get("full_name", submission.student_name)
        if hasattr(submission, "student_email"):
            submission.student_email = data.get("email", submission.student_email)
        submission.save()
        return redirect("registrations:submission_detail", pk=submission.pk)

    return render(request, "registrations/spark_fill_form.html", _spark_context(template_obj, submission.data or {}))

# REGISTRATION_SAVE_ACTIONS_START
from django.contrib.auth.decorators import login_required as _reg_login_required
from django.views.decorators.http import require_POST as _reg_require_POST


def _reg_safe_message(request, level, text):
    try:
        from django.contrib import messages
        getattr(messages, level)(request, text)
    except Exception:
        pass


def _reg_fields(model):
    return {field.name for field in model._meta.fields}


def _reg_template_qs(request):
    qs = RegistrationFormTemplate.objects.all()
    _t = _reg_user_tenant(request)
    if _t is not None:
        qs = qs.filter(tenant=_t)
    return qs


def _reg_submission_qs(request):
    qs = RegistrationSubmission.objects.select_related("template").all()
    _t = _reg_user_tenant(request)
    if _t is not None:
        qs = qs.filter(tenant=_t)
    return qs


def _reg_post_data(request):
    data = {}
    skip = {"csrfmiddlewaretoken", "id_image_data"}

    for key in request.POST.keys():
        if key in skip:
            continue
        values = request.POST.getlist(key)
        data[key] = values if len(values) > 1 else (values[0] if values else "")

    # لا نحفظ صورة الهوية نفسها على السيرفر، فقط نثبت أن المستخدم رفعها.
    if request.POST.get("id_image_data"):
        data["id_image_uploaded"] = "yes"

    return data


def _reg_spark_context(template_obj, posted=None):
    if "_spark_context" in globals():
        try:
            ctx = _spark_context(template_obj, posted or {})
            if "registration_types" not in ctx:
                schema = getattr(template_obj, "schema", None) or {}
                ctx["registration_types"] = schema.get("registration_types", [
                    {"value": "New Student", "ar": "طالب جديد", "en": "New Student"},
                    {"value": "Re-enroll", "ar": "تجديد داخل المعهد", "en": "Re-enroll"},
                    {"value": "Online", "ar": "عن بعد", "en": "Online"},
                    {"value": "One to one (VIP)", "ar": "One to one (VIP)", "en": "One to one (VIP)"},
                ])
            return ctx
        except Exception:
            pass

    schema = getattr(template_obj, "schema", None) or {}
    return {
        "template_obj": template_obj,
        "posted": posted or {},
        "general_english_courses": globals().get("SPARK_GENERAL_ENGLISH", []),
        "other_courses": globals().get("SPARK_OTHER_COURSES", []),
        "days": globals().get("SPARK_DAYS", []),
        "payment_methods": globals().get("SPARK_PAYMENT_METHODS", []),
        "durations": globals().get("SPARK_DURATIONS", []),
        "registration_types": schema.get("registration_types", [
            {"value": "New Student", "ar": "طالب جديد", "en": "New Student"},
            {"value": "Re-enroll", "ar": "تجديد داخل المعهد", "en": "Re-enroll"},
            {"value": "Online", "ar": "عن بعد", "en": "Online"},
            {"value": "One to one (VIP)", "ar": "One to one (VIP)", "en": "One to one (VIP)"},
        ]),
    }


@_reg_login_required
def spark_fill_form(request, pk):
    from django.shortcuts import get_object_or_404, render, redirect

    template_obj = get_object_or_404(_reg_template_qs(request).filter(is_active=True), pk=pk)

    if request.method == "POST":
        data = _reg_post_data(request)

        missing = []
        for key, label in {
            "full_name": "Full name",
            "mobile": "Mobile Number",
            "email": "Email",
        }.items():
            if not str(data.get(key, "")).strip():
                missing.append(label)

        if missing:
            _reg_safe_message(request, "error", "يرجى تعبئة الحقول المطلوبة: " + "، ".join(missing))
            return render(request, "registrations/spark_fill_form.html", _reg_spark_context(template_obj, data))

        fields = _reg_fields(RegistrationSubmission)
        kwargs = {"template": template_obj, "data": data}

        if "student_name" in fields:
            kwargs["student_name"] = data.get("full_name", "")
        if "student_email" in fields:
            kwargs["student_email"] = data.get("email", "")
        if "signature_data" in fields:
            kwargs["signature_data"] = data.get("signature_data", "")
        if "status" in fields:
            kwargs["status"] = "submitted"
        if "created_by" in fields and request.user.is_authenticated:
            kwargs["created_by"] = request.user
        if "tenant" in fields:
            kwargs["tenant"] = getattr(template_obj, "tenant", None)

        submission = RegistrationSubmission.objects.create(**kwargs)
        _reg_safe_message(request, "success", "تم حفظ التسجيل بنجاح.")
        return redirect("registrations:submission_detail", pk=submission.pk)

    return render(request, "registrations/spark_fill_form.html", _reg_spark_context(template_obj))


def _reg_pdf_bytes(request, submission):
    from django.template.loader import render_to_string
    from weasyprint import HTML

    ctx = {
        "submission": submission,
        "data": submission.data or {},
        "registration_types": (getattr(submission.template, "schema", None) or {}).get("registration_types", []),
    }
    html = render_to_string("registrations/spark_submission_pdf.html", ctx, request=request)
    return HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()


@_reg_login_required
def submission_detail(request, pk):
    from django.shortcuts import get_object_or_404, render
    submission = get_object_or_404(_reg_submission_qs(request), pk=pk)
    data = submission.data or {}
    return render(request, "registrations/submission_detail.html", {
        "submission": submission,
        "data": data,
        "display_items": _reg_display_items(data),
    })

@_reg_login_required
def submission_pdf(request, pk):
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404

    submission = get_object_or_404(_reg_submission_qs(request), pk=pk)
    pdf = _reg_pdf_bytes(request, submission)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="registration-{submission.pk}.pdf"'
    return response


@_reg_login_required
def spark_submission_pdf(request, pk):
    return submission_pdf(request, pk)


@_reg_login_required
def submission_edit(request, pk):
    from django.shortcuts import get_object_or_404, render, redirect

    submission = get_object_or_404(_reg_submission_qs(request), pk=pk)
    data = dict(submission.data or {})

    if request.method == "POST":
        for item in _reg_editable_items(data):
            key = item["key"]
            if key in request.POST:
                data[key] = request.POST.get(key, "")

        submission.data = data

        fields = _reg_fields(RegistrationSubmission)
        if "student_name" in fields:
            submission.student_name = data.get("full_name", submission.student_name)
        if "student_email" in fields:
            submission.student_email = data.get("email", submission.student_email)

        submission.save()
        _reg_safe_message(request, "success", "تم تعديل التسجيل.")
        return redirect("registrations:submission_detail", pk=submission.pk)

    return render(request, "registrations/submission_edit.html", {
        "submission": submission,
        "editable_items": _reg_editable_items(data),
    })

@_reg_login_required
@_reg_require_POST
def submission_delete(request, pk):
    from django.shortcuts import get_object_or_404, redirect
    submission = get_object_or_404(_reg_submission_qs(request), pk=pk)
    submission.delete()
    _reg_safe_message(request, "success", "تم حذف التسجيل.")
    return redirect("registrations:dashboard")


@_reg_login_required
@_reg_require_POST
def submission_email(request, pk):
    from django.shortcuts import get_object_or_404, redirect
    submission = get_object_or_404(_reg_submission_qs(request), pk=pk)
    data = submission.data or {}
    recipient = (request.POST.get("recipient") or getattr(submission, "student_email", "") or data.get("email") or "").strip()
    if not recipient:
        _reg_safe_message(request, "error", "لا يوجد بريد إلكتروني لإرسال التسجيل.")
        return redirect("registrations:submission_detail", pk=submission.pk)
    # جلب مفاتيح EmailJS: شركة التسجيل إن وُجدت، وإلا مفاتيح المستخدم الحالي (المدير)
    tenant = getattr(submission, "tenant", None)
    t_sid = t_tid = t_pub = t_priv = ""
    if tenant is not None:
        t_sid = (getattr(tenant, "emailjs_service_id", "") or "").strip()
        t_tid = (getattr(tenant, "emailjs_template_id", "") or "").strip()
        t_pub = (getattr(tenant, "emailjs_public_key", "") or "").strip()
        t_priv = (getattr(tenant, "emailjs_private_key", "") or "").strip()
    # إن لم تكتمل مفاتيح الشركة، نستخدم إعدادات المستخدم الحالي (المدير)
    _use_user_cfg = not (t_sid and t_tid and t_pub)
    if _use_user_cfg:
        try:
            from apps.campaigns.emailjs_service import get_user_emailjs_config
            _ucfg = get_user_emailjs_config(request.user)
            t_sid = t_sid or _ucfg.get("service_id", "")
            t_tid = t_tid or _ucfg.get("template_id", "")
            t_pub = t_pub or _ucfg.get("public_key", "")
            t_priv = t_priv or _ucfg.get("private_key", "")
        except Exception:
            pass
    if not (t_sid and t_tid and t_pub):
        _reg_safe_message(request, "error", "لم يتم إعداد بريد EmailJS. يرجى ضبط إعدادات الإرسال أولاً.")
        return redirect("registrations:submission_detail", pk=submission.pk)
    try:
        from apps.campaigns.emailjs_service import send_via_emailjs
        from django.utils import timezone
        student_name = data.get("full_name", "") or "الطالب"
        pdf_url = request.build_absolute_uri(f"/registrations/submissions/{submission.pk}/spark-pdf/")
        html = f'''
        <div style="font-family:Arial,sans-serif;direction:rtl;max-width:600px;margin:0 auto">
          <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center;border-radius:12px 12px 0 0">
            <h2 style="margin:0">معهد سبارك لتعليم اللغات</h2>
            <p style="margin:8px 0 0">Spark Language Institute</p>
          </div>
          <div style="padding:24px;background:#f8fafc;border-radius:0 0 12px 12px">
            <p>عزيزي {student_name}،</p>
            <p>تم استلام طلب تسجيلك بنجاح. رقم الطلب: <b>#{submission.pk}</b></p>
            <p>يمكنك عرض وتحميل نموذج التسجيل من الرابط التالي:</p>
            <p style="text-align:center;margin:22px 0">
              <a href="{pdf_url}" style="background:#0b4ea2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:bold">عرض نموذج التسجيل</a>
            </p>
            <p style="color:#667085;font-size:13px">شكراً لاختيارك معهد سبارك. نتمنى لك التوفيق.</p>
          </div>
        </div>
        '''
        # نمرّر user لقراءة مفاتيح المدير، أو service/template للشركة إن توفّرت
        _send_kwargs = dict(
            to_email=recipient,
            to_name=student_name,
            subject=f"تأكيد التسجيل - معهد سبارك - طلب #{submission.pk}",
            body_html=html,
            body_text=f"تم استلام طلب تسجيلك #{submission.pk}. الرابط: {pdf_url}",
            user=request.user,
        )
        if not _use_user_cfg:
            _send_kwargs["service_id"] = t_sid
            _send_kwargs["template_id"] = t_tid
        result = send_via_emailjs(**_send_kwargs)
        if result.get("success"):
            if hasattr(submission, "email_sent_at"):
                submission.email_sent_at = timezone.now()
                submission.save(update_fields=["email_sent_at"])
            _reg_safe_message(request, "success", "تم إرسال التسجيل إلى البريد الإلكتروني.")
        else:
            _reg_safe_message(request, "error", f"تعذر إرسال البريد: {result.get('error', 'خطأ غير معروف')}")
    except Exception as exc:
        _reg_safe_message(request, "error", f"تعذر إرسال البريد: {exc}")
    return redirect("registrations:submission_detail", pk=submission.pk)
# REGISTRATION_SAVE_ACTIONS_END



# REGISTRATION_SAFE_DISPLAY_HELPERS_START
def _reg_display_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v is not None)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    value = str(value)
    if value.startswith("data:image"):
        return ""
    return value


def _reg_display_items(data):
    hidden = {"id_image_data"}
    items = []
    for key, value in (data or {}).items():
        if key in hidden:
            continue
        val = _reg_display_value(value)
        if not val:
            continue
        items.append({"key": key, "label": key.replace("_", " "), "value": val})
    return items


def _reg_editable_items(data):
    protected = {
        "signature_data",
        "advisor_signature_data",
        "director_signature_data",
        "id_image_uploaded",
        "id_image_data",
    }
    items = []
    for key, value in (data or {}).items():
        if key in protected:
            continue
        val = _reg_display_value(value)
        if val.startswith("data:image"):
            continue
        items.append({"key": key, "label": key.replace("_", " "), "value": val})
    return items
# REGISTRATION_SAFE_DISPLAY_HELPERS_END




def ocr_id_image_disabled(request):
    import json, base64, re
    from django.http import JsonResponse
    from PIL import Image, ImageEnhance
    import pytesseract, io
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body)
        img_data = body.get('image', '')
        if ',' in img_data:
            img_data = img_data.split(',')[1]
        img_bytes = base64.b64decode(img_data)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        text = pytesseract.image_to_string(img, lang='eng', config='--psm 3 --oem 3')
        fields = {}
        import re as _re
        name = _re.search(r'Name[.:\s]+([A-Za-z ]{5,50})', text, _re.I)
        if name: fields['full_name'] = name.group(1).strip()
        nat = _re.search(r'Nationality[.:\s]+([A-Za-z]{3,25})', text, _re.I)
        if nat: fields['nationality'] = nat.group(1).strip()
        sex = _re.search(r'Sex[.:\s]+([MF])', text, _re.I)
        if sex: fields['gender'] = 'Male' if sex.group(1).upper() == 'M' else 'Female'
        dob = _re.search(r'(?:Date of Birth|Birth)[.:\s]*(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})', text, _re.I)
        if dob: fields['date_of_birth'] = f"{dob.group(3)}-{dob.group(2).zfill(2)}-{dob.group(1).zfill(2)}"
        exp = _re.search(r'Expiry[.:\s]*(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})', text, _re.I)
        if exp: fields['expiry_date'] = f"{exp.group(3)}-{exp.group(2).zfill(2)}-{exp.group(1).zfill(2)}"
        id_num = _re.search(r'(\d{3}[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d)', text)
        if id_num: fields['id_number'] = id_num.group(1)
        occ = _re.search(r'Occupation[.:\s]+([A-Za-z ]{3,40})', text, _re.I)
        if occ: fields['occupation'] = occ.group(1).strip()
        emp = _re.search(r'Employer[.:\s]+([A-Za-z .]{3,50})', text, _re.I)
        if emp: fields['employer'] = emp.group(1).strip()
        return JsonResponse({'success': True, 'result': {'fields': fields, 'raw': text[:300]}})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def clients_page(request):
    from .models import RegClient, RegEmployee
    from django.utils import timezone
    import datetime, json
    from apps.platform_core.models import TenantMembership
    _t = _reg_user_tenant(request)
    if _t and not (_t.modules or {}).get("registrations", False):
        return redirect("dashboard:home")

    membership = None
    limited = False
    can_manage = False
    if _t:
        membership = TenantMembership.objects.filter(tenant=_t, user=request.user).first()
        if membership:
            limited = bool((membership.permissions or {}).get("reg_clients_limited"))
            can_manage = bool(membership.is_tenant_admin)

    def _own_clients():
        qs = RegClient.objects.select_related("employee", "created_by")
        return qs.filter(tenant=_t) if _t else qs.filter(tenant__isnull=True)

    def _own_employees():
        qs = RegEmployee.objects.all()
        return qs.filter(tenant=_t) if _t else qs.filter(tenant__isnull=True)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "save_client":
            pk = request.POST.get("client_id")
            if limited:
                if pk:
                    _own_clients().filter(pk=pk).update(
                        notes=(request.POST.get("notes") or "").strip(),
                        reminder_date=(request.POST.get("reminder_date") or None) or None,
                    )
                return redirect("registrations:clients_page")
            name = (request.POST.get("name") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            if name and phone:
                emp = _own_employees().filter(pk=request.POST.get("employee") or 0).first()
                reg_emp = _own_employees().filter(pk=request.POST.get("registered_by") or 0).first()
                data = dict(
                    name=name, phone=phone,
                    registered_by=reg_emp,
                    status=request.POST.get("status") or "potential",
                    employee=emp,
                    notes=(request.POST.get("notes") or "").strip(),
                    reminder_date=(request.POST.get("reminder_date") or None) or None,
                )
                if pk:
                    _own_clients().filter(pk=pk).update(**data)
                else:
                    RegClient.objects.create(tenant=_t, created_by=request.user, **data)
            return redirect("registrations:clients_page")
        elif action == "delete_client" and not limited:
            _own_clients().filter(pk=request.POST.get("client_id")).delete()
            return redirect("registrations:clients_page")
        elif action == "add_employee" and not limited:
            ename = (request.POST.get("emp_name") or "").strip()
            if ename and not _own_employees().filter(name=ename).exists():
                RegEmployee.objects.create(tenant=_t, name=ename)
            return redirect("registrations:clients_page")
        elif action == "delete_employee" and not limited:
            _own_employees().filter(pk=request.POST.get("emp_id")).delete()
            return redirect("registrations:clients_page")
        elif action == "toggle_limited" and can_manage:
            mb = TenantMembership.objects.filter(tenant=_t, pk=request.POST.get("member_id")).first()
            if mb and not mb.is_tenant_admin:
                p = dict(mb.permissions or {})
                p["reg_clients_limited"] = not p.get("reg_clients_limited", False)
                mb.permissions = p
                mb.save()
            return redirect("registrations:clients_page")
        return redirect("registrations:clients_page")

    today = timezone.localdate()
    tomorrow = today + datetime.timedelta(days=1)
    reminders = _own_clients().filter(reminder_date__in=[today, tomorrow]).order_by("reminder_date")

    edit_client = None
    if request.GET.get("edit"):
        edit_client = _own_clients().filter(pk=request.GET["edit"]).first()

    members = TenantMembership.objects.filter(tenant=_t).select_related("user") if (can_manage and _t) else []

    phones_map = {cl.phone: {"name": cl.name, "id": cl.pk} for cl in _own_clients()}
    return render(request, "registrations/clients.html", {
        "phones_json": json.dumps(phones_map, ensure_ascii=False),
        "clients": _own_clients(),
        "employees": _own_employees(),
        "reminders": reminders,
        "reminders_count": reminders.count(),
        "edit_client": edit_client,
        "status_choices": RegClient.STATUS_CHOICES,
        "today": today,
        "limited": limited,
        "can_manage": can_manage,
        "members": members,
    })
