import re
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import MailingList, Recipient, UploadBatch, UnsubscribeList



def _check_owner(obj, request):
    """Raise 404-like redirect if user does not own the object."""
    from django.http import Http404
    if not request.user.is_superuser and getattr(obj, 'owner_id', None) and obj.owner_id != request.user.id:
        raise Http404('غير مصرح')
    return obj

def _owned(qs, request):
    """Return only objects owned by the user, unless superuser."""
    if request.user.is_superuser:
        return qs
    return qs.filter(owner=request.user)

EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$')

def is_valid_email(email):
    return bool(EMAIL_RE.match(str(email).strip()))

def detect_email_column(df):
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['email','mail','بريد','إيميل','ايميل']):
            sample = df[col].dropna().astype(str).head(10)
            if sample.apply(is_valid_email).any():
                return col
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(20)
        if sample.apply(is_valid_email).mean() > 0.5:
            return col
    return None

@login_required
def list_view(request):
    mailing_lists = _owned(MailingList.objects.all(), request)
    search = request.GET.get('q','')
    if search:
        mailing_lists = mailing_lists.filter(name__icontains=search)
    return render(request, 'recipients/list_view.html', {'mailing_lists': mailing_lists, 'search': search})

@login_required
def list_create(request):
    if request.method == 'POST':
        name = request.POST.get('name','').strip()
        desc = request.POST.get('description','').strip()
        if not name:
            messages.error(request, 'اسم القائمة مطلوب.')
        else:
            ml = MailingList.objects.create(owner=request.user, name=name, description=desc)
            messages.success(request, f'تم إنشاء القائمة "{name}".')
            return redirect('recipients:list_detail', pk=ml.pk)
    return render(request, 'recipients/list_form.html')

@login_required
def list_detail(request, pk):
    ml = get_object_or_404(MailingList, pk=pk)
    _check_owner(ml, request)
    recipients = ml.recipients.filter(is_active=True)
    search = request.GET.get('q','')
    status = request.GET.get('status','')
    if search:
        recipients = recipients.filter(Q(name__icontains=search)|Q(email__icontains=search))
    if status == 'unsubscribed':
        recipients = recipients.filter(is_unsubscribed=True)
    elif status == 'active':
        recipients = recipients.filter(is_unsubscribed=False)
    return render(request, 'recipients/list_detail.html', {'ml': ml, 'recipients': recipients, 'search': search, 'status': status, 'batches': ml.upload_batches.order_by('-created_at')[:10]})

@login_required
def recipient_add(request, list_pk):
    ml = get_object_or_404(MailingList, pk=list_pk)
    if request.method == 'POST':
        emails_raw = request.POST.get('emails','').strip()
        name = request.POST.get('name','').strip()
        phone = request.POST.get('phone','').strip()
        lines = [e.strip() for e in emails_raw.replace(',','\n').splitlines() if e.strip()]
        added = dupes = invalid = 0
        for line in lines:
            if is_valid_email(line):
                _, created = Recipient.objects.get_or_create(mailing_list=ml, email=line.lower(), defaults={'name': name if len(lines)==1 else '', 'phone': phone})
                if created:
                    added += 1
                else:
                    dupes += 1
            else:
                invalid += 1
        messages.success(request, f'مُضاف: {added} | مكرر: {dupes} | غير صالح: {invalid}')
        return redirect('recipients:list_detail', pk=list_pk)
    return render(request, 'recipients/recipient_form.html', {'ml': ml})

@login_required
def recipient_edit(request, pk):
    r = get_object_or_404(Recipient, pk=pk)
    if request.method == 'POST':
        r.name = request.POST.get('name','').strip()
        r.email = request.POST.get('email','').strip().lower()
        r.phone = request.POST.get('phone','').strip()
        r.custom_field_1 = request.POST.get('custom_field_1','').strip()
        r.custom_field_2 = request.POST.get('custom_field_2','').strip()
        r.save()
        messages.success(request, 'تم التحديث.')
        return redirect('recipients:list_detail', pk=r.mailing_list_id)
    return render(request, 'recipients/recipient_edit.html', {'r': r})

@login_required
def recipient_delete(request, pk):
    r = get_object_or_404(Recipient, pk=pk)
    list_pk = r.mailing_list_id
    r.delete()
    messages.success(request, 'تم الحذف.')
    return redirect('recipients:list_detail', pk=list_pk)

@login_required
def upload_file(request, list_pk):
    ml = get_object_or_404(MailingList, pk=list_pk)
    if request.method == 'POST':
        f = request.FILES.get('file')
        if not f:
            messages.error(request, 'لم يتم اختيار ملف.')
            return redirect('recipients:list_detail', pk=list_pk)
        ext = f.name.rsplit('.',1)[-1].lower()
        if ext not in ('xlsx','xls','csv','tsv','ods'):
            messages.error(request, 'نوع الملف غير مدعوم.')
            return redirect('recipients:list_detail', pk=list_pk)
        batch = UploadBatch.objects.create(mailing_list=ml, file=f, original_name=f.name, status='pending')
        try:
            if ext in ('xlsx','xls','ods'):
                df = pd.read_excel(batch.file.path, dtype=str)
            else:
                df = pd.read_csv(batch.file.path, dtype=str, encoding='utf-8-sig')
            df.columns = [str(c).strip() for c in df.columns]
            df = df.dropna(how='all')
            batch.total_rows = len(df)
            batch.save(update_fields=['total_rows'])
        except Exception as e:
            batch.status = 'failed'
            batch.error_report = [str(e)]
            batch.save()
            messages.error(request, f'خطأ: {e}')
            return redirect('recipients:list_detail', pk=list_pk)
        email_col = detect_email_column(df)
        if email_col:
            batch.email_column = email_col
            batch.status = 'processing'
            batch.save()
            return _process_upload(request, batch, df, email_col, ml)
        else:
            request.session[f'upload_batch_{batch.id}'] = {'columns': list(df.columns), 'preview': df.head(5).to_dict(orient='records')}
            batch.status = 'pending'
            batch.save()
            return redirect('recipients:upload_choose_column', list_pk=list_pk, batch_pk=batch.id)
    return redirect('recipients:list_detail', pk=list_pk)

def _process_upload(request, batch, df, email_col, ml):
    added = dupes = invalid = 0
    errors = []
    def find_col(keywords):
        for col in df.columns:
            if any(k in col.lower() for k in keywords):
                return col
        return None
    name_col = find_col(['name','اسم','الاسم'])
    phone_col = find_col(['phone','mobile','هاتف','جوال'])
    for idx, row in df.iterrows():
        email = str(row.get(email_col,'')).strip().lower()
        if not is_valid_email(email):
            invalid += 1
            errors.append({'row': idx+2, 'email': email, 'reason': 'غير صالح'})
            continue
        if UnsubscribeList.objects.filter(email=email).exists():
            dupes += 1
            continue
        name = str(row.get(name_col,'')).strip() if name_col else ''
        phone = str(row.get(phone_col,'')).strip() if phone_col else ''
        _, created = Recipient.objects.get_or_create(mailing_list=ml, email=email, defaults={'name': name, 'phone': phone})
        if created:
            added += 1
        else:
            dupes += 1
    batch.status = 'done'
    batch.imported = added
    batch.duplicates = dupes
    batch.invalid = invalid
    batch.error_report = errors[:100]
    batch.save()
    messages.success(request, f'✅ مُضاف {added} | مكرر {dupes} | غير صالح {invalid}')
    return redirect('recipients:list_detail', pk=ml.pk)

@login_required
def upload_choose_column(request, list_pk, batch_pk):
    ml = get_object_or_404(MailingList, pk=list_pk)
    batch = get_object_or_404(UploadBatch, pk=batch_pk)
    session_data = request.session.get(f'upload_batch_{batch_pk}', {})
    if request.method == 'POST':
        email_col = request.POST.get('email_column','').strip()
        if email_col:
            ext = batch.original_name.rsplit('.',1)[-1].lower()
            if ext in ('xlsx','xls','ods'):
                df = pd.read_excel(batch.file.path, dtype=str)
            else:
                df = pd.read_csv(batch.file.path, dtype=str, encoding='utf-8-sig')
            df.columns = [str(c).strip() for c in df.columns]
            df = df.dropna(how='all')
            batch.email_column = email_col
            batch.status = 'processing'
            batch.save()
            return _process_upload(request, batch, df, email_col, ml)
    return render(request, 'recipients/choose_column.html', {'ml': ml, 'batch': batch, 'columns': session_data.get('columns',[]), 'preview': session_data.get('preview',[])})

@login_required
def unsubscribe_list_view(request):
    return render(request, 'recipients/unsubscribe_list.html', {'unsubs': UnsubscribeList.objects.order_by('-created_at')})

def unsubscribe_public(request, email):
    UnsubscribeList.objects.get_or_create(email=email.lower())
    Recipient.objects.filter(email=email.lower()).update(is_unsubscribed=True)
    return render(request, 'recipients/unsubscribed.html', {'email': email})


from apps.recipients.cleaner import analyze_email

@login_required
def clean_list(request, pk):
    ml = get_object_or_404(MailingList, pk=pk)
    results = {'valid':[], 'invalid':[], 'disposable':[], 'typo':[]}
    for r in ml.recipients.all():
        a = analyze_email(r.email)
        a['recipient'] = r
        results[a['status']].append(a)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'remove_bad':
            ids = [x['recipient'].id for x in results['invalid']+results['disposable']]
            Recipient.objects.filter(id__in=ids).delete()
            messages.success(request, f'تم حذف {len(ids)} إيميل غير صالح/وهمي.')
            return redirect('recipients:list_detail', pk=pk)
        elif action == 'fix_typos':
            fixed = 0
            for x in results['typo']:
                r = x['recipient']
                r.email = x['suggestion']
                r.save()
                fixed += 1
            messages.success(request, f'تم تصحيح {fixed} إيميل.')
            return redirect('recipients:list_detail', pk=pk)
    return render(request, 'recipients/clean_list.html', {'ml':ml,'results':results})


@login_required
def segment_list(request, pk):
    ml = get_object_or_404(MailingList, pk=pk)
    recipients = ml.recipients.filter(is_active=True, is_unsubscribed=False)
    has_phone = request.GET.get('has_phone')
    course = request.GET.get('course', '').strip()
    name_contains = request.GET.get('name_contains', '').strip()
    if has_phone == '1':
        recipients = recipients.exclude(phone='')
    elif has_phone == '0':
        recipients = recipients.filter(phone='')
    if course:
        recipients = recipients.filter(custom_field_1__icontains=course)
    if name_contains:
        recipients = recipients.filter(name__icontains=name_contains)

    if request.method == 'POST':
        new_name = request.POST.get('segment_name', '').strip()
        if new_name:
            new_ml = MailingList.objects.create(name=new_name, description=f'شريحة من: {ml.name}')
            count = 0
            for r in recipients:
                Recipient.objects.get_or_create(mailing_list=new_ml, email=r.email,
                    defaults={'name':r.name,'phone':r.phone,'custom_field_1':r.custom_field_1,'custom_field_2':r.custom_field_2})
                count += 1
            messages.success(request, f'تم إنشاء شريحة "{new_name}" بـ {count} مستلم.')
            return redirect('recipients:list_detail', pk=new_ml.pk)

    return render(request, 'recipients/segment_list.html', {
        'ml': ml, 'recipients': recipients[:200], 'total': recipients.count(),
        'has_phone': has_phone, 'course': course, 'name_contains': name_contains,
    })
