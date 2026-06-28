
import re

from django.http import HttpResponseForbidden


def _clean_key(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _truthy(value):
    return value is True or str(value).lower() in {"1", "true", "yes", "on"}


def template_permission_keys(template_obj):
    keys = set()

    pk = getattr(template_obj, "pk", None)
    if pk:
        keys.add(str(pk))

    for attr in ["slug", "code", "name", "name_ar", "name_en", "title"]:
        value = getattr(template_obj, attr, "")
        key = _clean_key(value)
        if key:
            keys.add(key)

    joined = " ".join(keys)
    if "spark" in joined or "سبارك" in joined:
        keys.add("spark")
        keys.add("spark_form")
        keys.add("spark_language_institute")

    return keys


def normalize_registration_permissions(raw):
    raw = raw or {}
    if not isinstance(raw, dict):
        raw = {}

    forms = {}
    for source_key in ["forms", "form_permissions", "model_permissions"]:
        source = raw.get(source_key)
        if isinstance(source, dict):
            forms.update(source)

    # ملاحظة أمنية: صلاحية رؤية اللوحة (view) أو غيرها لا تمنح فتح النماذج.
    # كل نموذج يُفتح فقط عبر forms.<key> صراحة (مثل forms.spark).

    # توافق مع محاولة الصلاحيات المفصلة السابقة إن وجدت.
    if _truthy(raw.get("spark_form")) or _truthy(raw.get("spark_fill")):
        forms["spark"] = True

    dashboard = _truthy(raw.get("dashboard")) or _truthy(raw.get("view")) or _truthy(raw.get("settings"))

    return {
        "dashboard": dashboard,
        "forms": forms,
        "raw": raw,
    }


def form_allowed_by_permissions(raw, template_obj):
    perms = normalize_registration_permissions(raw)
    forms = perms["forms"]

    if _truthy(forms.get("*")):
        return True

    keys = template_permission_keys(template_obj)
    return any(_truthy(forms.get(key)) for key in keys)


def _membership_for_user(user):
    try:
        from apps.platform_core.navigation import active_membership_for
        return active_membership_for(user)
    except Exception:
        return None


def _registration_raw_permissions(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    if user.is_superuser:
        return {"dashboard": True, "forms": {"*": True}}

    membership = _membership_for_user(user)
    if not membership:
        return {}

    return (membership.permissions or {}).get("registrations", {})


def dashboard_allowed(request):
    user = getattr(request, "user", None)
    if user and user.is_superuser:
        return True

    raw = _registration_raw_permissions(request)
    return bool(normalize_registration_permissions(raw)["dashboard"])


def template_allowed(request, template_obj):
    user = getattr(request, "user", None)
    if user and user.is_superuser:
        return True

    raw = _registration_raw_permissions(request)
    return form_allowed_by_permissions(raw, template_obj)


def submission_template(submission):
    for attr in ["template", "form_template", "registration_template"]:
        value = getattr(submission, attr, None)
        if value is not None:
            return value
    return None


def submission_allowed(request, submission):
    template_obj = submission_template(submission)
    if template_obj is None:
        return dashboard_allowed(request)
    return template_allowed(request, template_obj)


def request_allowed_by_path(request):
    path = (request.path or "").rstrip("/")

    if path == "/registrations":
        return dashboard_allowed(request)

    try:
        from apps.registrations.models import RegistrationFormTemplate, RegistrationSubmission
    except Exception:
        return False

    match = re.search(r"/registrations/templates/(\d+)/", request.path or "")
    if match:
        template_obj = RegistrationFormTemplate.objects.filter(pk=int(match.group(1))).first()
        return bool(template_obj and template_allowed(request, template_obj))

    match = re.search(r"/registrations/submissions/(\d+)/", request.path or "")
    if match:
        submission = RegistrationSubmission.objects.filter(pk=int(match.group(1))).first()
        return bool(submission and submission_allowed(request, submission))

    # إنشاء قالب جديد أو إعدادات عامة: تحتاج لوحة التسجيلات.
    return dashboard_allowed(request)


def no_registration_permission_response():
    return HttpResponseForbidden("""
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>صلاحية غير متاحة</title>
<style>
body{margin:0;background:#eef4fb;font-family:Tahoma,Arial,sans-serif;color:#102033}
.card{max-width:560px;margin:90px auto;background:#fff;border:1px solid #d9e4f2;border-radius:14px;padding:34px;text-align:center;box-shadow:0 18px 45px rgba(11,78,162,.12)}
h1{margin:0 0 12px;color:#0b4ea2;font-size:28px}
p{color:#667085;line-height:1.8}
a{display:inline-block;margin-top:14px;background:#0b4ea2;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px}
</style>
</head>
<body>
<div class="card">
<h1>هذا النموذج غير مفعّل لحسابك</h1>
<p>يرجى التواصل مع مدير المنصة لتفعيل صلاحية هذا النموذج.</p>
<a href="/workspace/">العودة لمساحة العمل</a>
</div>
</body>
</html>
""")


class RegistrationModelPermissionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""

        if not (path.rstrip("/") == "/registrations" or path.startswith("/registrations/")):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.is_superuser:
            return self.get_response(request)

        if not request_allowed_by_path(request):
            return no_registration_permission_response()

        return self.get_response(request)
