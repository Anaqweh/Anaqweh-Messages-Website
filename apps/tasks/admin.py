from django.contrib import admin

# Register your models here.


# تعريب (عرض فقط)
try:
    from .models import TaskWorkflowTemplate, TaskWorkflowStage, Task, TaskStageLog, TaskComment, TaskAttachment
    for _m,(_s,_p) in {
        TaskWorkflowTemplate:("قالب سير عمل","قوالب سير العمل"),
        TaskWorkflowStage:("مرحلة","مراحل سير العمل"),
        Task:("مهمة","المهام"),
        TaskStageLog:("سجل مرحلة","سجلات المراحل"),
        TaskComment:("تعليق","التعليقات"),
        TaskAttachment:("مرفق","المرفقات"),
    }.items():
        _m._meta.verbose_name=_s; _m._meta.verbose_name_plural=_p
except Exception:
    pass
