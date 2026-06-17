import io, csv
import xlsxwriter
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from apps.campaigns.models import Campaign, EmailLog
from apps.recipients.models import MailingList, Recipient

@login_required
def reports_dashboard(request):
    campaigns = Campaign.objects.all()
    total_logs = EmailLog.objects.count()
    total_sent = EmailLog.objects.filter(status='sent').count()
    stats = {
        'total_campaigns': campaigns.count(),
        'completed': campaigns.filter(status='completed').count(),
        'running': campaigns.filter(status='running').count(),
        'total_sent': total_sent,
        'total_failed': EmailLog.objects.filter(status='failed').count(),
        'total_pending': EmailLog.objects.filter(status__in=['pending','sending']).count(),
        'total_recipients': Recipient.objects.filter(is_active=True).count(),
        'total_lists': MailingList.objects.count(),
        'overall_rate': round((total_sent/total_logs)*100,1) if total_logs>0 else 0,
    }
    campaign_stats = [{'campaign': c, 'total': c.total_recipients, 'sent': c.sent_count, 'failed': c.failed_count, 'pending': c.pending_count, 'rate': c.success_rate} for c in campaigns]
    failed_logs = EmailLog.objects.filter(status='failed').select_related('campaign')[:50]
    return render(request, 'reports/dashboard.html', {'stats': stats, 'campaign_stats': campaign_stats, 'failed_logs': failed_logs})

@login_required
def campaign_report(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    logs = campaign.logs.order_by('-created_at')
    status_filter = request.GET.get('status','')
    if status_filter:
        logs = logs.filter(status=status_filter)
    return render(request, 'reports/campaign_report.html', {'campaign': campaign, 'logs': logs, 'status_filter': status_filter, 'status_choices': EmailLog.STATUS_CHOICES})

@login_required
def export_campaign_csv(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="campaign_{pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(['الاسم','البريد','الحالة','وقت الإرسال','المحاولات','سبب الفشل'])
    for log in campaign.logs.all():
        writer.writerow([log.recipient_name, log.recipient_email, log.get_status_display(), log.sent_at.strftime('%Y-%m-%d %H:%M') if log.sent_at else '', log.attempts, log.error_message])
    return response

@login_required
def export_campaign_excel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('تقرير')
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1e3a6e', 'font_color': 'white', 'border': 1})
    cell_fmt = workbook.add_format({'border': 1})
    headers = ['الاسم','البريد','الحالة','وقت الإرسال','المحاولات','سبب الفشل']
    for col, h in enumerate(headers):
        worksheet.write(0, col, h, header_fmt)
    for row, log in enumerate(campaign.logs.all(), start=1):
        worksheet.write(row, 0, log.recipient_name, cell_fmt)
        worksheet.write(row, 1, log.recipient_email, cell_fmt)
        worksheet.write(row, 2, log.get_status_display(), cell_fmt)
        worksheet.write(row, 3, log.sent_at.strftime('%Y-%m-%d %H:%M') if log.sent_at else '', cell_fmt)
        worksheet.write(row, 4, log.attempts, cell_fmt)
        worksheet.write(row, 5, log.error_message, cell_fmt)
    worksheet.set_column(0, 5, 25)
    workbook.close()
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="campaign_{pk}.xlsx"'
    return response


from django.http import JsonResponse
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

def analytics_api(request):
    """JSON data for charts."""
    today = timezone.now().date()
    days = []
    sent_data = []
    opened_data = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        days.append(day.strftime('%m/%d'))
        qs = EmailLog.objects.filter(sent_at__date=day)
        sent_data.append(qs.filter(status__in=['sent','opened','clicked']).count())
        opened_data.append(qs.filter(status__in=['opened','clicked']).count())
    status_counts = {
        'sent': EmailLog.objects.filter(status='sent').count(),
        'opened': EmailLog.objects.filter(status='opened').count(),
        'clicked': EmailLog.objects.filter(status='clicked').count(),
        'failed': EmailLog.objects.filter(status='failed').count(),
        'pending': EmailLog.objects.filter(status__in=['pending','sending']).count(),
    }
    return JsonResponse({'days': days, 'sent': sent_data, 'opened': opened_data, 'status': status_counts})
