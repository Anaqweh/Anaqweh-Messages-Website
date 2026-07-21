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

def _company_user_ids(request):
    """يرجع قائمة بمعرفات كل مستخدمي شركة المستخدم الحالي (للعزل حسب الشركة)."""
    from apps.platform_core.navigation import active_membership_for
    from apps.platform_core.models import TenantMembership
    membership = active_membership_for(request.user)
    if not membership:
        return [request.user.id]
    user_ids = list(
        TenantMembership.objects.filter(tenant=membership.tenant)
        .values_list("user_id", flat=True)
    )
    if request.user.id not in user_ids:
        user_ids.append(request.user.id)
    return user_ids

def _owned(qs, request):
    if request.user.is_superuser:
        return qs
    return qs.filter(owner_id__in=_company_user_ids(request))

def _owned_logs(qs, request):
    """عزل سجلات الإيميل حسب الشركة (عبر الحملة المالكة)."""
    if request.user.is_superuser:
        return qs
    return qs.filter(campaign__owner_id__in=_company_user_ids(request))


def _email_permission_ok(request):
    """صلاحية قسم الحملات/الإرسال الذكي. المدير العام دائماً مسموح."""
    if request.user.is_superuser:
        return True
    try:
        from apps.platform_core.navigation import active_membership_for, permissions_for_membership
        m = active_membership_for(request.user)
        if not m:
            return False
        perms = permissions_for_membership(m) or {}
        return bool(perms.get("email", {}).get("view"))
    except Exception:
        return False


def _email_denied_response():
    from django.http import HttpResponseForbidden
    return HttpResponseForbidden("هذه الميزة غير مفعّلة لحسابك. يرجى التواصل مع مدير المنصة.")

@login_required
def dashboard(request):
    # استعلام واحد فقط بدلاً من مرتين — تحسين الأداء
    _camp = _owned(Campaign.objects.all(), request)
    _logs = _owned_logs(EmailLog.objects.all(), request)
    campaigns = _camp.select_related('mailing_list').order_by('-created_at')[:10]
    from django.db.models import Count
    from django.db.models import Q as _Q
    stats = {
        'total_campaigns': _camp.count(),
        'running': _camp.filter(status='running').count(),
        'completed': _camp.filter(status='completed').count(),
        'total_emails_sent': _logs.filter(status='sent').count(),
        'total_failed': _logs.filter(status='failed').count(),
        'total_pending': _logs.filter(status__in=['pending','sending']).count(),
    }
    # عزل recent_logs حسب الشركة أيضاً
    recent_logs = _logs.select_related('campaign').order_by('-created_at')[:20]
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
    templates = _owned(EmailTemplate.objects.filter(is_active=True), request)
    lists = _owned(MailingList.objects.all(), request)
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
    if not _email_permission_ok(request):
        return _email_denied_response()
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
    if not _email_permission_ok(request):
        return _email_denied_response()
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
    if not _email_permission_ok(request):
        return _email_denied_response()
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

@login_required
def smart_send_lists(request):
    """قوائم المستخدم المحفوظة مع عدد المستلمين (قراءة فقط)."""
    from django.http import JsonResponse
    from django.db.models import Count
    from apps.recipients.models import MailingList
    qs = MailingList.objects.all() if request.user.is_superuser else MailingList.objects.filter(owner=request.user)
    qs = qs.annotate(n=Count('recipients')).order_by('-updated_at')
    return JsonResponse({'lists': [{'id': l.pk, 'name': l.name, 'count': l.n} for l in qs[:100]]})


@login_required
def smart_send_list_recipients(request):
    """شريحة مستلمين من قائمة محفوظة: count أو from/to (قراءة فقط، معزولة بالمالك)."""
    from django.http import JsonResponse
    from apps.recipients.models import MailingList, Recipient
    try:
        list_id = int(request.GET.get('list_id') or 0)
    except ValueError:
        return JsonResponse({'error': 'bad list_id'}, status=400)
    ql = MailingList.objects.all() if request.user.is_superuser else MailingList.objects.filter(owner=request.user)
    ml = ql.filter(pk=list_id).first()
    if not ml:
        return JsonResponse({'error': 'قائمة غير موجودة'}, status=404)
    qs = Recipient.objects.filter(mailing_list=ml).order_by('id')
    total = qs.count()
    f = request.GET.get('from'); t = request.GET.get('to'); cnt = request.GET.get('count')
    try:
        if f and t:
            f = max(1, int(f)); t = min(int(t), total)
            qs = qs[f-1:t]
        elif cnt:
            qs = qs[:max(0, min(int(cnt), total))]
    except ValueError:
        return JsonResponse({'error': 'أرقام غير صالحة'}, status=400)
    data = [{'email': r.email, 'name': r.name or ''} for r in qs[:5000]]
    return JsonResponse({'total': total, 'returned': len(data), 'recipients': data})

@login_required
def smart_send_log_start(request):
    import json as _j
    from django.http import JsonResponse
    from .models import SmartSendBatch, SmartSendRecipientLog
    if request.method != 'POST':
        return JsonResponse({'error': 'POST'}, status=405)
    try:
        d = _j.loads(request.body)
        recs = d.get('recipients', [])
        b = SmartSendBatch.objects.create(owner=request.user, subject=(d.get('subject') or '')[:300], body_html=d.get('body_html') or '', total=len(recs))
        seen = set()
        rows = []
        for r in recs:
            em = (r.get('email') or '').strip()
            if em and em not in seen:
                seen.add(em)
                rows.append(SmartSendRecipientLog(batch=b, email=em, name=(r.get('name') or '')[:200]))
        SmartSendRecipientLog.objects.bulk_create(rows, ignore_conflicts=True)
        track = {l['email']: [l['id'], _track_sig(l['id'])] for l in SmartSendRecipientLog.objects.filter(batch=b).values('id', 'email')}
        return JsonResponse({'batch_id': b.pk, 'track': track})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def smart_send_log_update(request):
    import json as _j
    from django.http import JsonResponse
    from .models import SmartSendBatch, SmartSendRecipientLog
    try:
        d = _j.loads(request.body)
        b = SmartSendBatch.objects.filter(owner=request.user, pk=d.get('batch_id')).first()
        if not b:
            return JsonResponse({'error': 'batch'}, status=404)
        for r in d.get('results', []):
            SmartSendRecipientLog.objects.filter(batch=b, email=(r.get('email') or '').strip()).update(
                status='sent' if r.get('ok') else 'failed', error=(r.get('err') or '')[:200])
        b.success = b.logs.filter(status='sent').count()
        b.failed = b.logs.filter(status='failed').count()
        pending = b.logs.filter(status='pending').count()
        b.status = 'done' if pending == 0 else 'partial'
        b.save()
        return JsonResponse({'success': b.success, 'failed': b.failed, 'pending': pending})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def smart_send_batch_pending(request):
    from django.http import JsonResponse
    from .models import SmartSendBatch
    b = SmartSendBatch.objects.filter(owner=request.user, pk=request.GET.get('batch_id') or 0).first()
    if not b:
        return JsonResponse({'error': 'الدفعة غير موجودة'}, status=404)
    pend = list(b.logs.filter(status='pending').values('email', 'name'))
    track = {p['email']: [p['id'], _track_sig(p['id'])] for p in b.logs.filter(status='pending').values('id', 'email')}
    return JsonResponse({'batch_id': b.pk, 'subject': b.subject, 'body_html': b.body_html, 'pending': pend, 'track': track})


@login_required
def smart_send_history(request):
    from django.http import HttpResponse
    from .models import SmartSendBatch
    rows = ''
    for b in SmartSendBatch.objects.filter(owner=request.user).order_by('-id')[:30]:
        pend = b.total - b.success - b.failed
        _op = b.logs.filter(opened_at__isnull=False).count()
        if b.success:
            _rate = round(_op * 100 / b.success)
            _rc = '#0f9d58' if _rate >= 15 else ('#b45309' if _rate >= 5 else '#e24b4a')
            _rtxt = '%d%%' % _rate
        else:
            _rc, _rtxt = '#94a3b8', '\u2014'
        resume = ('<a href="/smart-send/?resume=%d" style="background:#b45309;color:#fff;border-radius:8px;padding:5px 14px;text-decoration:none;font-size:12px;font-weight:700">\u0627\u0633\u062a\u0626\u0646\u0627\u0641 (%d)</a>' % (b.pk, pend)) if pend > 0 else '<span style="color:#0f9d58;font-weight:700">\u2713 \u0645\u0643\u062a\u0645\u0644</span>'
        rows += ('<tr><td style="padding:10px;border-bottom:1px solid #f1f5f9;font-size:13px">%s</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9;font-weight:700"><a href="/smart-send/history/%d/" style="color:#0b4ea2;text-decoration:none">%s</a></td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9">%d</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#0f9d58;font-weight:700">%d</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#e24b4a;font-weight:700">%d</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#0369a1;font-weight:700">%d</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9;color:%s;font-weight:800">%s</td>'
                 '<td style="padding:10px;border-bottom:1px solid #f1f5f9">%s</td></tr>') % (
                 b.created_at.strftime('%Y-%m-%d %H:%M'), b.pk, (b.subject or '\u2014')[:45], b.total, b.success, b.failed, _op, _rc, _rtxt, resume)
    html = ('<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>\u0633\u062c\u0644 \u0627\u0644\u0625\u0631\u0633\u0627\u0644</title>'
            '<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"></head>'
            '<body style="font-family:Tajawal,Arial;background:#f6f9fc;margin:0;padding:26px">'
            '<div style="max-width:900px;margin:0 auto;background:#fff;border-radius:16px;padding:24px;box-shadow:0 4px 16px rgba(15,36,68,.07)">'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">'
            '<h2 style="margin:0;color:#1e3a6e">\u0633\u062c\u0644 \u0627\u0644\u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0630\u0643\u064a</h2>'
            '<a href="/smart-send/" style="background:#0b4ea2;color:#fff;border-radius:10px;padding:9px 18px;text-decoration:none;font-weight:700">\u2190 \u0627\u0644\u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0630\u0643\u064a</a></div>'
            '<table style="width:100%%;border-collapse:collapse"><thead><tr style="background:#f8fafc">'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u062a\u0627\u0631\u064a\u062e</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u0645\u0648\u0636\u0648\u0639</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0646\u062c\u062d</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0641\u0634\u0644</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0641\u064f\u062a\u062d</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0646\u0633\u0628\u0629 \u0627\u0644\u0641\u062a\u062d</th>'
            '<th style="padding:10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u062d\u0627\u0644\u0629</th>'
            '</tr></thead><tbody>%s</tbody></table>'
            '%s</div></body></html>') % (rows, '' if rows else '<p style="text-align:center;color:#94a3b8;padding:30px">\u0644\u0627 \u0625\u0631\u0633\u0627\u0644\u0627\u062a \u0645\u0633\u062c\u0644\u0629 \u0628\u0639\u062f</p>')
    return HttpResponse(html)

@login_required
def smart_send_schedule(request):
    import json as _j
    from django.http import JsonResponse
    from django.utils import timezone as _tz
    import datetime as _dt
    from .models import SmartSendBatch, SmartSendRecipientLog
    if request.method != 'POST':
        return JsonResponse({'error': 'POST'}, status=405)
    try:
        d = _j.loads(request.body)
        when = d.get('scheduled_at') or ''
        naive = _dt.datetime.strptime(when, '%Y-%m-%dT%H:%M')
        aware = _tz.make_aware(naive, _tz.get_current_timezone())
        if aware <= _tz.now():
            return JsonResponse({'error': 'اختر وقتاً مستقبلياً'}, status=400)
        recs = d.get('recipients', [])
        if not recs or not d.get('subject') or not d.get('body_html'):
            return JsonResponse({'error': 'بيانات ناقصة'}, status=400)
        b = SmartSendBatch.objects.create(owner=request.user, subject=(d.get('subject') or '')[:300],
                                          body_html=d.get('body_html') or '', total=len(recs),
                                          status='scheduled', scheduled_at=aware,
                                          delay=max(0, min(int(d.get('delay') or 3), 30)))
        seen = set(); rows = []
        for r in recs:
            em = (r.get('email') or '').strip()
            if em and em not in seen:
                seen.add(em)
                rows.append(SmartSendRecipientLog(batch=b, email=em, name=(r.get('name') or '')[:200]))
        SmartSendRecipientLog.objects.bulk_create(rows, ignore_conflicts=True)
        return JsonResponse({'batch_id': b.pk, 'scheduled_at': aware.strftime('%Y-%m-%d %H:%M')})
    except ValueError:
        return JsonResponse({'error': 'صيغة الوقت غير صحيحة'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def _track_sig(pk):
    import hashlib
    from django.conf import settings as _s
    return hashlib.sha1((str(pk) + _s.SECRET_KEY).encode()).hexdigest()[:10]


def track_open(request, pk, sig):
    from django.http import HttpResponse, Http404
    from django.utils import timezone as _tz
    from .models import SmartSendRecipientLog
    if sig != _track_sig(pk):
        raise Http404
    log = SmartSendRecipientLog.objects.filter(pk=pk).first()
    if log:
        if not log.opened_at:
            log.opened_at = _tz.now()
        log.open_count = (log.open_count or 0) + 1
        log.save(update_fields=["opened_at", "open_count", "updated_at"])
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    r = HttpResponse(gif, content_type="image/gif")
    r["Cache-Control"] = "no-store"
    return r

@login_required
def smart_send_batch_detail(request, pk):
    from django.http import HttpResponse, Http404
    from .models import SmartSendBatch
    q = SmartSendBatch.objects.all() if request.user.is_superuser else SmartSendBatch.objects.filter(owner=request.user)
    b = q.filter(pk=pk).first()
    if not b:
        raise Http404
    ST = {"sent": ("#e6f7ee", "#0f9d58", "\u0646\u062c\u062d"), "failed": ("#fdecec", "#e24b4a", "\u0641\u0634\u0644"), "pending": ("#f1f5f9", "#64748b", "\u0645\u0639\u0644\u0651\u0642")}
    rows = ""
    for i, l in enumerate(b.logs.order_by("id"), 1):
        bg, fg, txt = ST.get(l.status, ST["pending"])
        opened = ("\u2713 " + l.opened_at.strftime("%m-%d %H:%M") + " (\u00d7%d)" % (l.open_count or 1)) if l.opened_at else "\u2014"
        oc = "#0369a1" if l.opened_at else "#94a3b8"
        rows += ('<tr><td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;color:#94a3b8">%d</td>'
                 '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-weight:700" dir="ltr">%s</td>'
                 '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9">%s</td>'
                 '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9"><span style="background:%s;color:%s;border-radius:999px;padding:3px 12px;font-size:12px;font-weight:700">%s</span></td>'
                 '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;color:%s;font-weight:700;font-size:13px">%s</td>'
                 '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;color:#e24b4a;font-size:12px">%s</td></tr>') % (
                 i, l.email, l.name or "\u2014", bg, fg, txt, oc, opened, (l.error or "")[:60])
    opened_n = b.logs.filter(opened_at__isnull=False).count()
    html = ('<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>\u062a\u0641\u0627\u0635\u064a\u0644 \u0627\u0644\u0625\u0631\u0633\u0627\u0644</title>'
            '<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"></head>'
            '<body style="font-family:Tajawal,Arial;background:#f6f9fc;margin:0;padding:26px">'
            '<div style="max-width:980px;margin:0 auto;background:#fff;border-radius:16px;padding:24px;box-shadow:0 4px 16px rgba(15,36,68,.07)">'
            '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:6px">'
            '<h2 style="margin:0;color:#1e3a6e;font-size:1.2rem">%s</h2>'
            '<a href="/smart-send/history/" style="background:#eef2f7;color:#334155;border-radius:10px;padding:8px 16px;text-decoration:none;font-weight:700">\u2190 \u0627\u0644\u0633\u062c\u0644</a></div>'
            '<div style="color:#64748b;font-size:.85rem;margin-bottom:16px">%s &nbsp;\u2022&nbsp; \u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a: %d &nbsp;\u2022&nbsp; <span style="color:#0f9d58">\u0646\u062c\u062d: %d</span> &nbsp;\u2022&nbsp; <span style="color:#e24b4a">\u0641\u0634\u0644: %d</span> &nbsp;\u2022&nbsp; <span style="color:#0369a1">\u0641\u064f\u062a\u062d: %d</span></div>'
            '<div style="overflow-x:auto"><table style="width:100%%;border-collapse:collapse;min-width:640px"><thead><tr style="background:#f8fafc">'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">#</th>'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u0628\u0631\u064a\u062f</th>'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u0627\u0633\u0645</th>'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u062d\u0627\u0644\u0629</th>'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u0641\u062a\u062d</th>'
            '<th style="padding:9px 10px;text-align:right;font-size:12px;color:#475569">\u0627\u0644\u062e\u0637\u0623</th>'
            '</tr></thead><tbody>%s</tbody></table></div></div></body></html>') % (
            (b.subject or "\u0628\u0644\u0627 \u0645\u0648\u0636\u0648\u0639"), b.created_at.strftime("%Y-%m-%d %H:%M"), b.total, b.success, b.failed, opened_n, rows)
    return HttpResponse(html)
