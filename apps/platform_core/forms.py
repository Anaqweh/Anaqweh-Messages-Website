from django import forms

from .models import Tenant, default_permissions, default_tenant_limits, default_tenant_modules


MODULE_CHOICES = [
    ("email", "نظام البريد"),
    ("finance", "النظام المالي"),
    ("crm", "CRM"),
    ("accounting", "المحاسبة"),
    ("reports", "التقارير"),
    ("tasks", "المهام"),
    ("registrations", "النماذج والتسجيل"),
    ("stripe", "خدمة الدفع (Stripe)"),
]

LIMIT_FIELDS = [
    ("users", "عدد المستخدمين"),
    ("campaigns_per_month", "حملات شهريا"),
    ("contacts", "جهات الاتصال"),
    ("invoices_per_month", "فواتير شهريا"),
    ("storage_mb", "المساحة MB"),
]

TENANT_FIELDS = [
    "name",
    "slug",
    "status",
    "owner_name",
    "owner_email",
    "owner_phone",
    "domain",
    "plan_name",
    "subscription_starts_at",
    "subscription_ends_at",
]

def model_has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.fields)


class BootstrapMixin:
    def apply_bootstrap(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class TenantForm(BootstrapMixin, forms.ModelForm):
    for module_code, module_label in MODULE_CHOICES:
        locals()[f"module_{module_code}"] = forms.BooleanField(label=module_label, required=False)

    for limit_code, limit_label in LIMIT_FIELDS:
        locals()[f"limit_{limit_code}"] = forms.IntegerField(label=limit_label, required=False, min_value=0)

    class Meta:
        model = Tenant
        fields = [field for field in TENANT_FIELDS if model_has_field(Tenant, field)]
        widgets = {
            "subscription_starts_at": forms.DateInput(attrs={"type": "date"}),
            "subscription_ends_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        modules = default_tenant_modules()
        limits = default_tenant_limits()

        if self.instance and self.instance.pk:
            if model_has_field(Tenant, "modules") and self.instance.modules:
                modules.update(self.instance.modules)
            if model_has_field(Tenant, "limits") and self.instance.limits:
                limits.update(self.instance.limits)

        for module_code, _ in MODULE_CHOICES:
            self.fields[f"module_{module_code}"].initial = bool(modules.get(module_code))

        for limit_code, _ in LIMIT_FIELDS:
            self.fields[f"limit_{limit_code}"].initial = limits.get(limit_code)

        self.apply_bootstrap()

    def save(self, commit=True):
        tenant = super().save(commit=False)

        if model_has_field(Tenant, "modules"):
            tenant.modules = {
                module_code: bool(self.cleaned_data.get(f"module_{module_code}"))
                for module_code, _ in MODULE_CHOICES
            }

        if model_has_field(Tenant, "limits"):
            limits = default_tenant_limits()
            for limit_code, _ in LIMIT_FIELDS:
                value = self.cleaned_data.get(f"limit_{limit_code}")
                if value is not None:
                    limits[limit_code] = value
            tenant.limits = limits

        if commit:
            tenant.save()
            self.save_m2m()

        return tenant


class TenantManagerForm(BootstrapMixin, forms.Form):
    email = forms.EmailField(label="بريد المستخدم")
    username = forms.CharField(label="اسم المستخدم", required=False)
    full_name = forms.CharField(label="الاسم الكامل", required=False)
    password = forms.CharField(label="كلمة المرور", required=False, widget=forms.PasswordInput)
    role_name = forms.CharField(
        label="المسمى الوظيفي",
        required=False,
        help_text="مثال: محاسب، مبيعات، إداري، مدير فرع...",
    )
    is_tenant_admin = forms.BooleanField(label="مدير الشركة", required=False)
    perm_email = forms.BooleanField(label="البريد الإلكتروني", required=False, initial=True)
    perm_finance = forms.BooleanField(label="المالية", required=False)
    perm_crm = forms.BooleanField(label="CRM", required=False)
    perm_reports = forms.BooleanField(label="التقارير", required=False)
    perm_settings = forms.BooleanField(label="الإعدادات والمستخدمين", required=False)

    def __init__(self, *args, tenant_modules=None, **kwargs):
        super().__init__(*args, **kwargs)
        # نخفي الوحدات غير المتاحة للشركة
        if tenant_modules:
            module_map = {
                "email": "perm_email",
                "finance": "perm_finance",
                "crm": "perm_crm",
                "reports": "perm_reports",
            }
            for module, field in module_map.items():
                if not tenant_modules.get(module, False):
                    self.fields.pop(field, None)
        self.apply_bootstrap()

    def permissions_payload(self):
        permissions = default_permissions()
        mapping = {
            "email": self.cleaned_data.get("perm_email", False),
            "finance": self.cleaned_data.get("perm_finance", False),
            "crm": self.cleaned_data.get("perm_crm", False),
            "reports": self.cleaned_data.get("perm_reports", False),
            "settings": self.cleaned_data.get("perm_settings", False),
        }
        for section, enabled in mapping.items():
            if section not in permissions:
                continue
            for action in permissions[section]:
                permissions[section][action] = bool(enabled)
        return permissions

PERMISSION_LABELS = {
    "email": "البريد",
    "finance": "المالية",
    "crm": "CRM",
    "reports": "التقارير",
    "settings": "الإعدادات",
    "emailjs": "إعداد EmailJS",
}

ACTION_LABELS = {
    "view": "عرض",
    "create": "إضافة",
    "edit": "تعديل",
    "delete": "حذف",
    "send": "إرسال",
    "export": "تصدير",
    "manage_users": "إدارة المستخدمين",
}


class MembershipPermissionsForm(BootstrapMixin, forms.Form):
    def __init__(self, *args, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.membership = membership

        permissions = default_permissions()
        if membership is not None:
            member_permissions = getattr(membership, "permissions", None)
            if member_permissions:
                permissions.update(member_permissions)
            role = getattr(membership, "role", None)
            role_permissions = getattr(role, "permissions", None)
            if role_permissions and not member_permissions:
                permissions.update(role_permissions)

        self.permission_groups = []
        for section, actions in permissions.items():
            group_fields = []
            for action, enabled in actions.items():
                if isinstance(enabled, dict):
                    continue
                field_name = f"perm__{section}__{action}"
                self.fields[field_name] = forms.BooleanField(
                    label=ACTION_LABELS.get(action, action),
                    required=False,
                    initial=bool(enabled),
                )
                group_fields.append(field_name)

            if section == "registrations":
                reg_forms = actions.get("forms") if isinstance(actions.get("forms"), dict) else {}
                self.fields["spark_registration_form"] = forms.BooleanField(
                    label="نموذج تسجيل معهد سبارك",
                    required=False,
                    initial=bool(reg_forms.get("spark")),
                )
                group_fields.append("spark_registration_form")

            self.permission_groups.append({
                "code": section,
                "label": PERMISSION_LABELS.get(section, section),
                "fields": group_fields,
            })

        self.apply_bootstrap()

    def permissions_payload(self):
        permissions = default_permissions()

        for field_name, value in self.cleaned_data.items():
            if not field_name.startswith("perm__"):
                continue

            _, section, action = field_name.split("__", 2)
            permissions.setdefault(section, {})
            permissions[section][action] = bool(value)

        spark_on = bool(self.cleaned_data.get("spark_registration_form"))
        permissions.setdefault("registrations", {})
        reg_forms = permissions["registrations"].get("forms")
        if not isinstance(reg_forms, dict):
            reg_forms = {}
        reg_forms["spark"] = spark_on
        permissions["registrations"]["forms"] = reg_forms

        return permissions
