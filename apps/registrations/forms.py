import json
from django import forms

from .models import RegistrationFormTemplate, RegistrationSubmission, default_registration_schema


class RegistrationTemplateForm(forms.ModelForm):
    schema_json = forms.CharField(
        label="هيكل الأسئلة JSON",
        required=True,
        widget=forms.Textarea(attrs={"rows": 16}),
    )

    class Meta:
        model = RegistrationFormTemplate
        fields = ["name", "header_title", "header_subtitle", "logo", "is_active", "terms_text"]
        widgets = {
            "terms_text": forms.Textarea(attrs={"rows": 6}),
        }
        labels = {
            "name": "اسم القالب الداخلي",
            "header_title": "عنوان النموذج الأعلى",
            "header_subtitle": "الوصف تحت العنوان",
            "logo": "شعار النموذج",
            "is_active": "مفعل",
            "terms_text": "الشروط والنصوص",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        schema = default_registration_schema()
        if self.instance and self.instance.pk:
            schema = self.instance.schema or schema

        self.fields["schema_json"].initial = json.dumps(schema, ensure_ascii=False, indent=2)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

        self.fields["logo"].widget.attrs.update({"accept": "image/*"})

    def clean_schema_json(self):
        raw = self.cleaned_data["schema_json"]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"JSON غير صحيح: {exc}")

        if not isinstance(data, dict) or "sections" not in data:
            raise forms.ValidationError("يجب أن يحتوي JSON على sections.")

        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.schema = self.cleaned_data["schema_json"]
        if commit:
            obj.save()
        return obj


class DynamicRegistrationSubmissionForm(forms.Form):
    pass
