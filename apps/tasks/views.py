from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.utils import timezone
from .models import Task, TaskWorkflowTemplate, TaskWorkflowStage, TaskStageLog, TaskComment, TaskAttachment


def _task_tenant(request):
    try:
        from apps.platform_core.navigation import active_membership_for, is_platform_admin
        from apps.platform_core.models import Tenant
        user = request.user
        if is_platform_admin(user):
            tid = request.session.get('active_tenant_id')
            return Tenant.objects.get(pk=tid) if tid else None
        m = active_membership_for(user)
        return m.tenant if m else None
    except Exception:
        return None

def _task_qs(request):
    """يرجع مهام معزولة حسب الشركة (المدير العام يرى الكل)."""
    qs = Task.objects.all()
    t = _task_tenant(request)
    if t:
        return qs.filter(tenant=t)
    # غير المدير العام بلا شركة لا يرى شيئاً
    try:
        from apps.platform_core.navigation import is_platform_admin
        if not is_platform_admin(request.user):
            return qs.none()
    except Exception:
        return qs.none()
    return qs


@login_required
def task_dashboard(request):
    tenant = _task_tenant(request)
    qs = Task.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)
    today = timezone.now().date()
    context = {
        'total': qs.count(),
        'new': qs.filter(status='new').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'late': qs.filter(due_date__lt=today, status__in=['new','in_progress','pending_review','returned']).count(),
        'completed': qs.filter(status='completed').count(),
        'returned': qs.filter(status='returned').count(),
        'recent': qs[:8],
        'urgent': qs.filter(priority='urgent').exclude(status__in=['completed','cancelled'])[:5],
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_list(request):
    tenant = _task_tenant(request)
    qs = Task.objects.select_related('assigned_to', 'created_by', 'current_stage')
    if tenant:
        qs = qs.filter(tenant=tenant)
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    return render(request, 'tasks/task_list.html', {
        'tasks': qs, 'q': q, 'status': status, 'priority': priority,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    })


@login_required
def task_create(request):
    tenant = _task_tenant(request)
    workflows = TaskWorkflowTemplate.objects.filter(is_active=True)
    if tenant:
        workflows = workflows.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
    if request.method == 'POST':
        task = Task(
            tenant=tenant,
            created_by=request.user,
            title=request.POST.get('title', '').strip(),
            description=request.POST.get('description', '').strip(),
            task_type=request.POST.get('task_type', '').strip(),
            status=request.POST.get('status', 'new'),
            priority=request.POST.get('priority', 'medium'),
            notes=request.POST.get('notes', '').strip(),
            external_links=request.POST.get('external_links', '').strip(),
        )
        if request.POST.get('start_date'):
            task.start_date = request.POST.get('start_date')
        if request.POST.get('due_date'):
            task.due_date = request.POST.get('due_date')
        wf_id = request.POST.get('workflow_template')
        if wf_id:
            try:
                wf = TaskWorkflowTemplate.objects.get(pk=wf_id)
                task.workflow_template = wf
                first_stage = wf.stages.first()
                if first_stage:
                    task.current_stage = first_stage
            except TaskWorkflowTemplate.DoesNotExist:
                pass
        assigned_id = request.POST.get('assigned_to')
        if assigned_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            task.assigned_to = User.objects.filter(pk=assigned_id).first()
        task.save()
        messages.success(request, f'تم إنشاء المهمة: {task.title}')
        return redirect('tasks:task_detail', pk=task.pk)
    from django.contrib.auth import get_user_model
    users = get_user_model().objects.filter(is_active=True)
    return render(request, 'tasks/task_form.html', {
        'task': None, 'workflows': workflows, 'users': users,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    })


@login_required
def task_detail(request, pk):
    tenant = _task_tenant(request)
    task = get_object_or_404(_task_qs(request), pk=pk)
    stages = []
    if task.workflow_template:
        stages = task.workflow_template.stages.all()
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'stages': stages,
        'comments': task.comments.all(),
        'attachments': task.attachments.all(),
        'logs': task.stage_logs.all(),
    })


@login_required
def task_edit(request, pk):
    task = get_object_or_404(_task_qs(request), pk=pk)
    tenant = _task_tenant(request)
    workflows = TaskWorkflowTemplate.objects.filter(is_active=True)
    if request.method == 'POST':
        task.title = request.POST.get('title', task.title).strip()
        task.description = request.POST.get('description', '').strip()
        task.task_type = request.POST.get('task_type', '').strip()
        task.status = request.POST.get('status', task.status)
        task.priority = request.POST.get('priority', task.priority)
        task.notes = request.POST.get('notes', '').strip()
        task.external_links = request.POST.get('external_links', '').strip()
        task.return_reason = request.POST.get('return_reason', '').strip()
        if request.POST.get('start_date'):
            task.start_date = request.POST.get('start_date')
        if request.POST.get('due_date'):
            task.due_date = request.POST.get('due_date')
        assigned_id = request.POST.get('assigned_to')
        if assigned_id:
            from django.contrib.auth import get_user_model
            task.assigned_to = get_user_model().objects.filter(pk=assigned_id).first()
        task.save()
        messages.success(request, 'تم حفظ التعديلات')
        return redirect('tasks:task_detail', pk=task.pk)
    from django.contrib.auth import get_user_model
    users = get_user_model().objects.filter(is_active=True)
    return render(request, 'tasks/task_form.html', {
        'task': task, 'workflows': workflows, 'users': users,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    })


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(_task_qs(request), pk=pk)
    task.delete()
    messages.success(request, 'تم حذف المهمة')
    return redirect('tasks:task_list')


@login_required
@require_POST
def task_move_stage(request, pk):
    task = get_object_or_404(_task_qs(request), pk=pk)
    action = request.POST.get('action', '')
    note = request.POST.get('note', '').strip()
    old_stage = task.current_stage
    if action == 'next' and task.workflow_template:
        stages = list(task.workflow_template.stages.all())
        if old_stage:
            idx = next((i for i, s in enumerate(stages) if s.pk == old_stage.pk), -1)
            if idx < len(stages) - 1:
                task.current_stage = stages[idx + 1]
                task.status = 'in_progress'
            else:
                task.status = 'completed'
                task.completed_at = timezone.now()
        task.save()
    elif action == 'return':
        task.status = 'returned'
        task.return_reason = note
        task.save()
    elif action == 'complete':
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
    elif action == 'hold':
        task.status = 'on_hold'
        task.save()
    elif action in Task.STATUS_CHOICES[0]:
        task.status = action
        task.save()
    TaskStageLog.objects.create(
        task=task, from_stage=old_stage, to_stage=task.current_stage,
        action=action, notes=note, done_by=request.user
    )
    messages.success(request, 'تم تحديث حالة المهمة')
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_add_comment(request, pk):
    task = get_object_or_404(_task_qs(request), pk=pk)
    body = request.POST.get('body', '').strip()
    if body:
        TaskComment.objects.create(task=task, author=request.user, body=body)
        messages.success(request, 'تم إضافة التعليق')
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_add_attachment(request, pk):
    task = get_object_or_404(_task_qs(request), pk=pk)
    f = request.FILES.get('file')
    if f:
        TaskAttachment.objects.create(
            task=task, uploaded_by=request.user, file=f,
            name=request.POST.get('name', '') or f.name
        )
        messages.success(request, 'تم رفع الملف')
    return redirect('tasks:task_detail', pk=pk)


@login_required
def task_kanban(request):
    tenant = _task_tenant(request)
    qs = Task.objects.select_related('assigned_to', 'current_stage')
    if tenant:
        qs = qs.filter(tenant=tenant)
    columns = {}
    for status, label in Task.STATUS_CHOICES:
        columns[status] = {'label': label, 'tasks': qs.filter(status=status)}
    return render(request, 'tasks/kanban.html', {'columns': columns})


@login_required
def workflow_list(request):
    tenant = _task_tenant(request)
    qs = TaskWorkflowTemplate.objects.prefetch_related('stages')
    if tenant:
        qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
    return render(request, 'tasks/workflow_list.html', {'workflows': qs})


@login_required
def workflow_create(request):
    tenant = _task_tenant(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'اسم القالب مطلوب')
            return redirect('tasks:workflow_list')
        wf = TaskWorkflowTemplate.objects.create(
            tenant=tenant, name=name,
            description=request.POST.get('description', '').strip(),
            created_by=request.user,
        )
        stage_names = request.POST.getlist('stage_name')
        stage_roles = request.POST.getlist('stage_role')
        for i, (sname, srole) in enumerate(zip(stage_names, stage_roles)):
            sname = sname.strip()
            if sname:
                TaskWorkflowStage.objects.create(
                    template=wf, name=sname, role_required=srole.strip(), order=i
                )
        messages.success(request, f'تم إنشاء قالب: {name}')
        return redirect('tasks:workflow_list')
    return render(request, 'tasks/workflow_form.html', {'wf': None})


@login_required
def workflow_edit(request, pk):
    tenant = _task_tenant(request)
    # عزل: تعديل قوالب الشركة فقط (المدير العام يعدّل الكل)
    _wf_qs = TaskWorkflowTemplate.objects.all()
    try:
        from apps.platform_core.navigation import is_platform_admin
        if not is_platform_admin(request.user):
            _wf_qs = _wf_qs.filter(tenant=tenant) if tenant else _wf_qs.none()
    except Exception:
        _wf_qs = _wf_qs.filter(tenant=tenant) if tenant else _wf_qs.none()
    wf = get_object_or_404(_wf_qs, pk=pk)
    if request.method == 'POST':
        wf.name = request.POST.get('name', wf.name).strip()
        wf.description = request.POST.get('description', '').strip()
        wf.save()
        wf.stages.all().delete()
        stage_names = request.POST.getlist('stage_name')
        stage_roles = request.POST.getlist('stage_role')
        for i, (sname, srole) in enumerate(zip(stage_names, stage_roles)):
            sname = sname.strip()
            if sname:
                TaskWorkflowStage.objects.create(
                    template=wf, name=sname, role_required=srole.strip(), order=i
                )
        messages.success(request, 'تم تحديث القالب')
        return redirect('tasks:workflow_list')
    return render(request, 'tasks/workflow_form.html', {'wf': wf})
