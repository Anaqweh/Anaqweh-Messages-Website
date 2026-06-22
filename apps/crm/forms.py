from django import forms
from .models import CRMCompany, CRMContact, CRMDeal, CRMTask

class BootstrapForm(forms.ModelForm):
    def _style(self):
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")

class CompanyForm(BootstrapForm):
    class Meta:
        model = CRMCompany
        fields = ["name","status","source","industry","website","email","phone","country","city","address","trn","owner","notes"]
        widgets = {"address": forms.Textarea(attrs={"rows":2}), "notes": forms.Textarea(attrs={"rows":3})}
    def __init__(self,*a,**k): super().__init__(*a,**k); self._style()

class ContactForm(BootstrapForm):
    class Meta:
        model = CRMContact
        fields = ["company","full_name","job_title","email","phone","whatsapp","source","owner","notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows":3})}
    def __init__(self,*a,**k): super().__init__(*a,**k); self._style()

class DealForm(BootstrapForm):
    class Meta:
        model = CRMDeal
        fields = ["company","contact","title","stage","value","currency","probability","expected_close_date","owner","notes"]
        widgets = {"expected_close_date": forms.DateInput(attrs={"type":"date"}), "notes": forms.Textarea(attrs={"rows":3})}
    def __init__(self,*a,**k): super().__init__(*a,**k); self._style()

class TaskForm(BootstrapForm):
    class Meta:
        model = CRMTask
        fields = ["company","contact","deal","title","task_type","status","priority","due_at","assigned_to","notes"]
        widgets = {"due_at": forms.DateTimeInput(attrs={"type":"datetime-local"}), "notes": forms.Textarea(attrs={"rows":3})}
    def __init__(self,*a,**k): super().__init__(*a,**k); self._style()
