import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import Campaign, EmailLog
from apps.templates_mgr.models import EmailTemplate
from apps.recipients.models import MailingList
from .tasks import run_campaign_task, send_test_email_task
from apps.accounts.audit import log_action



def _guard_campaign(campaign, request):
    from django.http import Http404
    if not request.user.is_superuser and campaign.owner_id and campaign.owner_id != request.user.id:
        raise Http404('غير مصرح')

def _owned(qs, request):
    if request.user.is_superuser:
        return qs
    return qs.filter(owner=request.user)

@login_required
def dashboard(request):
    campaigns = _owned(Campaign.objects.all(), request)[:10]
    stats = {
        'total_campaigns': Campaign.objects.count(),
        'running': Campaign.objects.filter(status='running').count(),
        'completed': Campaign.objects.filter(status='completed').count(),
        'total_emails_sent': EmailLog.objects.filter(status='sent').count(),
        'total_failed': EmailLog.objects.filter(status='failed').count(),
        'total_pending': EmailLog.objects.filter(status__in=['pending','sending']).count(),
    }
    recent_logs = EmailLog.objects.select_related('campaign').order_by('-created_at')[:20]
    return render(request, 'campaigns/dashboard.html', {'campaigns': campaigns, 'stats': stats, 'recent_logs': recent_logs})

@login_required
def campaign_list(request):
    from django.db.models import Count, Sum

    qs = _owned(Campaign.objects.all(), request).select_related('mailing_list').prefetch_related('message_steps')
    status_filter = request.GET.get('status','')
    search = request.GET.get('q','')

    base_qs = qs
    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(Q(name__icontains=search)|Q(subject__icontains=search))

    stats = {
        'total': base_qs.count(),
        'running': base_qs.filter(status='running').count(),
        'scheduled': base_qs.filter(status='scheduled').count(),
        'completed': base_qs.filter(status='completed').count(),
        'sent': sum(c.sent_count for c in base_qs),
        'failed': sum(c.failed_count for c in base_qs),
    }

    return render(request, 'campaigns/campaign_list.html', {
        'campaigns': qs,
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
        'status_choices': Campaign.STATUS_CHOICES,
        'has_running_without_recipients': any(c.status == 'running' and c.total_recipients == 0 for c in base_qs),
    })

@login_required
def campaign_create(request):
    templates = EmailTemplate.objects.filter(is_active=True)
    lists = MailingList.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name','').strip()
        template_id = request.POST.get('template')
        list_id = request.POST.get('mailing_list')
        subject = request.POST.get('subject','').strip()
        body_html = request.POST.get('body_html','').strip()
        body_text = request.POST.get('body_text','').strip()
        scheduled_at = request.POST.get('scheduled_at','').strip()
        send_now = request.POST.get('send_now') == '1'
        if not name or not subject or not body_html or not list_id:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة.')
            return render(request, 'campaigns/campaign_form.html', {'templates': templates, 'lists': lists, 'supported_vars': EmailTemplate.SUPPORTED_VARS})
        campaign = Campaign.objects.create(owner=request.user, name=name, template_id=template_id or None, mailing_list_id=list_id, subject=subject, body_html=body_html, body_text=body_text, status='draft', scheduled_at=scheduled_at or None)
        from apps.campaigns.models import CampaignMessageStep
        step_titles = request.POST.getlist('step_title[]')
        step_subjects = request.POST.getlist('step_subject[]')
        step_htmls = request.POST.getlist('step_body_html[]')
        step_times = request.POST.getlist('step_send_at[]')
        for idx, step_subject in enumerate(step_subjects, start=1):
            step_subject = (step_subject or '').strip()
            step_html = (step_htmls[idx-1] if idx-1 < len(step_htmls) else '').strip()
            step_time = (step_times[idx-1] if idx-1 < len(step_times) else '').strip()
            step_title = (step_titles[idx-1] if idx-1 < len(step_titles) else '').strip()
            if not step_subject or not step_html:
                continue
            CampaignMessageStep.objects.create(
                campaign=campaign,
                step_number=idx,
                title=step_title or f'الرسالة {idx}',
                subject=step_subject,
                body_html=step_html,
                body_text='',
                send_at=step_time or None,
                is_active=True,
            )
        if send_now:
            campaign.status = 'running'
            campaign.save()
            run_campaign_task.delay(campaign.id)
            log_action(request, 'إطلاق حملة', f'الحملة: {name}')
            messages.success(request, f'تم إطلاق الحملة "{name}"!')
        elif scheduled_at:
            campaign.status = 'scheduled'
            campaign.save()
            messages.success(request, f'تمت جدولة الحملة "{name}".')
        else:
            messages.success(request, f'تم حفظ الحملة "{name}" كمسودة.')
        return redirect('campaigns:campaign_detail', pk=campaign.pk)
    return render(request, 'campaigns/campaign_form.html', {'templates': templates, 'lists': lists, 'supported_vars': EmailTemplate.SUPPORTED_VARS})

@login_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    _guard_campaign(campaign, request)
    _ = None if request.user.is_superuser or getattr(campaign,'owner_id',None) in (None,request.user.id) else __import__('django.http',fromlist=['Http404']).Http404()
    logs = campaign.logs.order_by('-created_at')
    status_filter = request.GET.get('status','')
    search = request.GET.get('q','')
    if status_filter:
        logs = logs.filter(status=status_filter)
    if search:
        logs = logs.filter(Q(recipient_email__icontains=search)|Q(recipient_name__icontains=search))
    stats = {'total': campaign.total_recipients, 'sent': campaign.sent_count, 'failed': campaign.failed_count, 'pending': campaign.pending_count, 'rate': campaign.success_rate}
    return render(request, 'campaigns/campaign_detail.html', {'campaign': campaign, 'logs': logs[:200], 'stats': stats, 'status_filter': status_filter, 'search': search})

@login_required
def campaign_action(request, pk, action):
    campaign = get_object_or_404(Campaign, pk=pk)
    _guard_campaign(campaign, request)
    _ = None if request.user.is_superuser or getattr(campaign,'owner_id',None) in (None,request.user.id) else __import__('django.http',fromlist=['Http404']).Http404()
    log_action(request, f'حملة: {action}', f'الحملة: {campaign.name}')
    if action == 'start' and campaign.status in ('draft','paused'):
        campaign.status = 'running'
        campaign.save()
        run_campaign_task.delay(campaign.id)
        messages.success(request, 'تم إطلاق الحملة.')
    elif action == 'pause' and campaign.status == 'running':
        campaign.status = 'paused'
        campaign.save()
        messages.warning(request, 'تم إيقاف الحملة مؤقتاً.')
    elif action == 'cancel' and campaign.status not in ('completed','cancelled'):
        campaign.status = 'cancelled'
        campaign.save()
        messages.error(request, 'تم إلغاء الحملة.')
    elif action == 'delete':
        campaign.delete()
        messages.success(request, 'تم حذف الحملة.')
        return redirect('campaigns:campaign_list')
    return redirect('campaigns:campaign_detail', pk=pk)

@login_required
def send_test_email(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        to_email = data.get('email','').strip()
        subject = data.get('subject','رسالة اختبار')
        body_html = data.get('body_html','')
        if not to_email:
            return JsonResponse({'success': False, 'error': 'البريد مطلوب'})
        result = send_test_email_task.delay(to_email=to_email, subject=subject, body_html=body_html)
        return JsonResponse({'success': True, 'task_id': result.id})
    return JsonResponse({'success': False, 'error': 'POST only'})

@login_required
def campaign_stats_api(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    _guard_campaign(campaign, request)
    _ = None if request.user.is_superuser or getattr(campaign,'owner_id',None) in (None,request.user.id) else __import__('django.http',fromlist=['Http404']).Http404()
    return JsonResponse({'status': campaign.status, 'total': campaign.total_recipients, 'sent': campaign.sent_count, 'failed': campaign.failed_count, 'pending': campaign.pending_count, 'rate': campaign.success_rate})


import json
import io
import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
def smart_send(request):
    """صفحة الإرسال الذكي — إدخال يدوي أو رفع إكسيل"""
    from apps.templates_mgr.models import EmailTemplate
    templates = _owned(EmailTemplate.objects.all(), request)
    # التحقق من إعدادات EmailJS
    emailjs_ok = False
    sender_email = ''
    try:
        cfg = request.user.emailjs_config
        emailjs_ok = cfg.is_configured
        sender_email = cfg.from_email or request.user.email
    except Exception:
        from django.conf import settings
        emailjs_ok = bool(getattr(settings, 'EMAILJS_SERVICE_ID', ''))
        sender_email = request.user.email
    return render(request, 'campaigns/smart_send.html', {
        'templates': templates,
        'emailjs_ok': emailjs_ok,
        'sender_email': sender_email,
    })


@login_required
def parse_excel(request):
    """تحليل ملف إكسيل واستخراج الإيميلات والأسماء"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'لم يتم رفع ملف'}, status=400)
    
    try:
        import openpyxl
        import csv
        
        recipients = []
        filename = file.name.lower()
        
        if filename.endswith('.csv'):
            content = file.read().decode('utf-8-sig', errors='replace')
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            headers = reader.fieldnames or []
        else:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            if not all_rows:
                return JsonResponse({'recipients': [], 'total': 0})
            headers = [str(h).strip() if h else '' for h in all_rows[0]]
            rows = []
            for row in all_rows[1:]:
                rows.append({headers[i]: str(row[i]).strip() if row[i] is not None else '' for i in range(len(headers))})
        
        # اكتشاف عمود الإيميل تلقائياً
        email_col = None
        name_col = None
        email_keywords = ['email', 'mail', 'بريد', 'ايميل', 'إيميل', 'e-mail', 'البريد']
        name_keywords = ['name', 'اسم', 'الاسم', 'first_name', 'fullname', 'full_name', 'الاسم الكامل']
        
        for h in headers:
            hl = str(h).lower().strip()
            if any(k in hl for k in email_keywords):
                email_col = h
                break
        
        for h in headers:
            hl = str(h).lower().strip()
            if any(k in hl for k in name_keywords):
                name_col = h
                break
        
        # إذا لم نجد عمود إيميل، نبحث في كل الخلايا عن صيغة إيميل
        email_pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
        
        for row in rows:
            email = ''
            name = ''
            
            if email_col and email_col in row:
                email = str(row[email_col]).strip()
            else:
                # بحث تلقائي في كل الأعمدة
                for val in row.values():
                    v = str(val).strip()
                    if email_pattern.match(v):
                        email = v
                        break
            
            if name_col and name_col in row:
                name = str(row[name_col]).strip()
            
            if email and email_pattern.match(email):
                recipients.append({'email': email, 'name': name})
        
        # إزالة المكررات
        seen = set()
        unique = []
        for r in recipients:
            if r['email'] not in seen:
                seen.add(r['email'])
                unique.append(r)
        
        return JsonResponse({
            'recipients': unique,
            'total': len(unique),
            'headers': headers,
            'email_col': email_col,
            'name_col': name_col,
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required  
def do_smart_send(request):
    """تنفيذ الإرسال الذكي"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        recipients = data.get('recipients', [])
        subject = data.get('subject', '')
        body_html = data.get('body_html', '')
        delay = int(data.get('delay', 2))
        
        if not recipients or not subject or not body_html:
            return JsonResponse({'error': 'بيانات ناقصة'}, status=400)
        
        from apps.campaigns.emailjs_service import send_via_emailjs
        import time
        
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        for rec in recipients:
            email = rec.get('email', '').strip()
            name = rec.get('name', '').strip()
            
            if not email:
                continue
            
            # تخصيص الرسالة بالاسم
            personalized_html = body_html
            if name:
                personalized_html = body_html.replace('{{name}}', name).replace('{{الاسم}}', name)
            else:
                personalized_html = body_html.replace('{{name}}', '').replace('{{الاسم}}', '').replace('عزيزي {{name}}،', '').replace('Dear {{name}},', '')
            
            result = send_via_emailjs(
                to_email=email,
                to_name=name or email,
                subject=subject,
                body_html=personalized_html,
                user=request.user,
            )
            
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({'email': email, 'error': result['error']})
            
            if delay > 0:
                time.sleep(delay)
        
        return JsonResponse(results)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
