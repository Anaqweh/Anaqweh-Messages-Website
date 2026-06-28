from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import RegistrationFormTemplate, RegistrationSubmission


def _membership_for_user(user):
    try:
        from apps.platform_core.navigation import active_membership_for
        return active_membership_for(user)
    except Exception:
        return None


def _can_access_registrations(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return False

    if getattr(user, "is_superuser", False):
        return True

    membership = _membership_for_user(user)
    if not membership:
        return False

    modules = getattr(membership.tenant, "modules", None) or {}
    perms = getattr(membership, "permissions", None) or {}
    reg = perms.get("registrations", {})

    return bool(
        getattr(membership, "is_tenant_admin", False)
        or modules.get("registrations")
        or reg.get("view")
        or reg.get("create")
        or reg.get("settings")
    )


def _tenant_for_request(request):
    if request.user.is_superuser:
        return None
    membership = _membership_for_user(request.user)
    return membership.tenant if membership else None


def _json_safe_post(post):
    data = {}
    for key in post.keys():
        if key == "csrfmiddlewaretoken":
            continue
        values = post.getlist(key)
        data[key] = values if len(values) > 1 else post.get(key)
    return data


def _submission_kwargs(request, template_obj, data):
    tenant = _tenant_for_request(request)
    fields = {f.name for f in RegistrationSubmission._meta.fields}
    kwargs = {}

    if "template" in fields:
        kwargs["template"] = template_obj
    if "form_template" in fields:
        kwargs["form_template"] = template_obj

    if "tenant" in fields:
        kwargs["tenant"] = tenant

    if "data" in fields:
        kwargs["data"] = data
    if "answers" in fields:
        kwargs["answers"] = data
    if "form_data" in fields:
        kwargs["form_data"] = data

    if "student_name" in fields:
        kwargs["student_name"] = data.get("full_name") or data.get("student_name") or data.get("name") or ""
    if "student_email" in fields:
        kwargs["student_email"] = data.get("email") or data.get("student_email") or ""
    if "student_phone" in fields:
        kwargs["student_phone"] = data.get("mobile") or data.get("phone") or data.get("student_phone") or ""

    if "created_by" in fields:
        kwargs["created_by"] = request.user
    if "user" in fields:
        kwargs["user"] = request.user

    return kwargs


def _spark_context(request, template_obj):
    try:
        from . import views
        if hasattr(views, "_spark_context"):
            return views._spark_context(template_obj)
    except Exception:
        pass

    return {
        "template_obj": template_obj,
        "template": template_obj,
    }


@login_required
def spark_fill_form(request, pk):
    if not _can_access_registrations(request):
        return redirect("/workspace/")

    template_obj = get_object_or_404(RegistrationFormTemplate, pk=pk)

    # إذا كان القالب مربوطاً بشركة، اسمح فقط لنفس الشركة. القوالب العامة تعمل لكل الشركات.
    tenant = _tenant_for_request(request)
    if hasattr(template_obj, "tenant_id") and template_obj.tenant_id and tenant and template_obj.tenant_id != tenant.id and not request.user.is_superuser:
        return redirect("/registrations/")

    if request.method == "POST":
        data = _json_safe_post(request.POST)
        submission = RegistrationSubmission.objects.create(**_submission_kwargs(request, template_obj, data))
        return redirect("registrations:submission_detail", pk=submission.pk)

    context = _spark_context(request, template_obj)
    context["template_obj"] = template_obj
    context["template"] = template_obj
    return render(request, "registrations/spark_fill_form.html", context)
