from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def login_view(request):
    if request.user.is_authenticated:
        return redirect('campaigns:dashboard')
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        password = request.POST.get('password','')
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            login(request, user)
            from apps.accounts.audit import log_action
            log_action(request, 'تسجيل دخول', f'دخل المستخدم {username}')
            return redirect(request.GET.get('next','campaigns:dashboard'))
        messages.error(request, 'بيانات الدخول غير صحيحة.')
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html')


from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test

User = get_user_model()

def is_superuser(u):
    return u.is_superuser

@user_passes_test(is_superuser)
def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})

@user_passes_test(is_superuser)
def user_create(request):
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        password = request.POST.get('password','').strip()
        role = request.POST.get('role','staff')
        if username and password:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'اسم المستخدم موجود مسبقاً.')
            else:
                u = User.objects.create_user(username=username, password=password)
                u.is_staff = True
                u.is_superuser = (role == 'admin')
                u.save()
                messages.success(request, f'تم إنشاء المستخدم {username}.')
                return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html')

@user_passes_test(is_superuser)
def user_delete(request, pk):
    u = User.objects.filter(pk=pk).first()
    if u and not u.is_superuser:
        u.delete()
        messages.success(request, 'تم حذف المستخدم.')
    else:
        messages.error(request, 'لا يمكن حذف مدير.')
    return redirect('accounts:user_list')


from apps.accounts.audit import AuditLog

@user_passes_test(is_superuser)
def audit_log_view(request):
    logs = AuditLog.objects.all()[:300]
    return render(request, 'accounts/audit_log.html', {'logs': logs})
