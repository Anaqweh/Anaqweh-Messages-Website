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

@login_required
def dashboard(request):
    campaigns = Campaign.objects.all()[:10]
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
    qs = Campaign.objects.all()
    status_filter = request.GET.get('status','')
    search = request.GET.get('q','')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(Q(name__icontains=search)|Q(subject__icontains=search))
    return render(request, 'campaigns/campaign_list.html', {'campaigns': qs, 'status_filter': status_filter, 'search': search, 'status_choices': Campaign.STATUS_CHOICES})

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
        campaign = Campaign.objects.create(name=name, template_id=template_id or None, mailing_list_id=list_id, subject=subject, body_html=body_html, body_text=body_text, status='draft', scheduled_at=scheduled_at or None)
        if send_now:
            campaign.status = 'running'
            campaign.save()
            run_campaign_task.delay(campaign.id)
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
    return JsonResponse({'status': campaign.status, 'total': campaign.total_recipients, 'sent': campaign.sent_count, 'failed': campaign.failed_count, 'pending': campaign.pending_count, 'rate': campaign.success_rate})
