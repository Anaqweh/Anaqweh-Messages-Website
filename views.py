from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EmailTemplate


@login_required
def template_list(request):
    templates = EmailTemplate.objects.all()
    return render(request, 'templates_mgr/template_list.html', {'templates': templates})


@login_required
def template_create(request):
    if request.method == 'POST':
        name      = request.POST.get('name', '').strip()
        subject   = request.POST.get('subject', '').strip()
        body_html = request.POST.get('body_html', '').strip()
        body_text = request.POST.get('body_text', '').strip()

        if not name or not subject or not body_html:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة.')
        else:
            t = EmailTemplate.objects.create(
                name=name, subject=subject,
                body_html=body_html, body_text=body_text,
            )
            messages.success(request, f'تم إنشاء القالب "{name}".')
            return redirect('templates_mgr:template_detail', pk=t.pk)

    return render(request, 'templates_mgr/template_form.html', {
        'supported_vars': EmailTemplate.SUPPORTED_VARS,
    })


@login_required
def template_detail(request, pk):
    t = get_object_or_404(EmailTemplate, pk=pk)
    return render(request, 'templates_mgr/template_detail.html', {
        't': t,
        'supported_vars': EmailTemplate.SUPPORTED_VARS,
    })


@login_required
def template_edit(request, pk):
    t = get_object_or_404(EmailTemplate, pk=pk)
    if request.method == 'POST':
        t.name      = request.POST.get('name', '').strip()
        t.subject   = request.POST.get('subject', '').strip()
        t.body_html = request.POST.get('body_html', '').strip()
        t.body_text = request.POST.get('body_text', '').strip()
        t.save()
        messages.success(request, 'تم تحديث القالب.')
        return redirect('templates_mgr:template_detail', pk=t.pk)

    return render(request, 'templates_mgr/template_form.html', {
        't': t,
        'supported_vars': EmailTemplate.SUPPORTED_VARS,
    })


@login_required
def template_delete(request, pk):
    t = get_object_or_404(EmailTemplate, pk=pk)
    t.delete()
    messages.success(request, 'تم حذف القالب.')
    return redirect('templates_mgr:template_list')
