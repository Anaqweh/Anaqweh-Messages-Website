from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EmailTemplate


def _owned(qs, request):
    if request.user.is_superuser:
        return qs
    return qs.filter(owner=request.user)

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
    t = get_object_or_404(EmailTemplate, pk=pk)
    return render(request, 'templates_mgr/template_detail.html', {'t': t, 'supported_vars': EmailTemplate.SUPPORTED_VARS})

@login_required
def template_edit(request, pk):
    t = get_object_or_404(EmailTemplate, pk=pk)
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
    t = get_object_or_404(EmailTemplate, pk=pk)
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
            t = EmailTemplate.objects.create(owner=request.user, name=name, subject=subject, body_html=body_html)
            messages.success(request, f'تم حفظ القالب "{name}".')
            return redirect('templates_mgr:template_detail', pk=t.pk)
    return render(request, 'templates_mgr/builder.html')
