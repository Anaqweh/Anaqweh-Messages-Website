from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer


@login_required
def customers(request):
    q = (request.GET.get('q') or '').strip()
    qs = Customer.objects.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q) | Q(company__icontains=q))
    return render(request, 'accounting/customers.html', {'customers': qs, 'q': q})


@login_required
def customer_create(request):
    if request.method == 'POST':
        Customer.objects.create(
            name=request.POST.get('name', '').strip() or 'عميل',
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            company=request.POST.get('company', '').strip(),
            address=request.POST.get('address', '').strip(),
            trn=request.POST.get('trn', '').strip(),
            notes=request.POST.get('notes', '').strip(),
        )
        return redirect('accounting:customers')
    return render(request, 'accounting/customer_form.html', {'customer': None})


@login_required
def customer_edit(request, pk):
    c = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        c.name = request.POST.get('name', '').strip() or c.name
        c.email = request.POST.get('email', '').strip()
        c.phone = request.POST.get('phone', '').strip()
        c.company = request.POST.get('company', '').strip()
        c.address = request.POST.get('address', '').strip()
        c.trn = request.POST.get('trn', '').strip()
        c.notes = request.POST.get('notes', '').strip()
        c.is_active = bool(request.POST.get('is_active'))
        c.save()
        return redirect('accounting:customer_detail', pk=c.pk)
    return render(request, 'accounting/customer_form.html', {'customer': c})


@login_required
def customer_detail(request, pk):
    c = get_object_or_404(Customer, pk=pk)
    invoices = c._sales_invoices().prefetch_related('items')
    return render(request, 'accounting/customer_detail.html', {'customer': c, 'invoices': invoices})


def _report_data(request):
    """يجمع بيانات التقرير - قراءة فقط من جداول الدفع/الفواتير."""
    from decimal import Decimal
    from django.utils import timezone
    from apps.payments.models import SalesInvoice, Expense
    today = timezone.localdate()
    start = request.GET.get('from', '')
    end = request.GET.get('to', '')
    invoices = SalesInvoice.objects.all()
    expenses = Expense.objects.all()
    if start:
        invoices = invoices.filter(issue_date__gte=start)
        expenses = expenses.filter(spent_at__gte=start)
    if end:
        invoices = invoices.filter(issue_date__lte=end)
        expenses = expenses.filter(spent_at__lte=end)
    invoices = list(invoices.prefetch_related('items'))
    paid = [i for i in invoices if i.status == 'paid']
    unpaid = [i for i in invoices if i.status == 'unpaid']
    revenue = sum((i.subtotal for i in paid), Decimal('0.00'))
    tax_collected = sum((i.tax_amount for i in paid), Decimal('0.00'))
    gross = sum((i.total for i in paid), Decimal('0.00'))
    total_expenses = sum((e.amount for e in expenses), Decimal('0.00'))
    net_profit = gross - total_expenses
    outstanding = sum((i.total for i in unpaid), Decimal('0.00'))
    return {
        'today': today, 'start': start, 'end': end,
        'invoices': invoices, 'paid': paid, 'unpaid': unpaid,
        'expenses': list(expenses),
        'revenue': revenue, 'tax_collected': tax_collected, 'gross': gross,
        'total_expenses': total_expenses, 'net_profit': net_profit,
        'outstanding': outstanding,
        'cnt_paid': len(paid), 'cnt_unpaid': len(unpaid), 'cnt_total': len(invoices),
    }


@login_required
def reports(request):
    data = _report_data(request)
    return render(request, 'accounting/reports.html', data)


def _export_rows(data):
    """صفوف موحّدة للتصدير."""
    header = ['رقم الفاتورة', 'النوع', 'العميل', 'الحالة', 'الفرعي', 'الضريبة', 'الإجمالي', 'العملة', 'تاريخ الإصدار']
    rows = []
    for i in data['invoices']:
        rows.append([
            i.invoice_number, i.get_kind_display(), i.customer_name,
            i.get_status_display(), float(i.subtotal), float(i.tax_amount),
            float(i.total), i.currency.upper(), i.issue_date.strftime('%Y-%m-%d'),
        ])
    return header, rows


@login_required
def reports_export_csv(request):
    import csv
    from django.http import HttpResponse
    data = _report_data(request)
    header, rows = _export_rows(data)
    resp = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    resp['Content-Disposition'] = 'attachment; filename="financial_report.csv"'
    resp.write('\ufeff')  # BOM لدعم العربية في Excel
    writer = csv.writer(resp)
    writer.writerow(header)
    writer.writerows(rows)
    writer.writerow([])
    writer.writerow(['الإيرادات', float(data['revenue'])])
    writer.writerow(['الضريبة المحصّلة', float(data['tax_collected'])])
    writer.writerow(['إجمالي المبيعات', float(data['gross'])])
    writer.writerow(['المصروفات', float(data['total_expenses'])])
    writer.writerow(['صافي الربح', float(data['net_profit'])])
    writer.writerow(['المستحقات القائمة', float(data['outstanding'])])
    return resp


@login_required
def reports_export_xlsx(request):
    import io
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    data = _report_data(request)
    header, rows = _export_rows(data)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'التقرير المالي'
    ws.sheet_view.rightToLeft = True
    hf = Font(bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='0B4EA2')
    ws.append(header)
    for c in ws[1]:
        c.font = hf
        c.fill = fill
    for r in rows:
        ws.append(r)
    ws.append([])
    summary = [
        ('الإيرادات', float(data['revenue'])),
        ('الضريبة المحصّلة', float(data['tax_collected'])),
        ('إجمالي المبيعات', float(data['gross'])),
        ('المصروفات', float(data['total_expenses'])),
        ('صافي الربح', float(data['net_profit'])),
        ('المستحقات القائمة', float(data['outstanding'])),
    ]
    for label, val in summary:
        ws.append([label, val])
        ws[ws.max_row][0].font = Font(bold=True)
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(width + 4, 40)
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="financial_report.xlsx"'
    return resp
