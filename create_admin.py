from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

User = get_user_model()


class Command(BaseCommand):
    help = 'Create default admin user from .env settings'

    def handle(self, *args, **kwargs):
        email    = config('ADMIN_EMAIL',    default='admin@inexc.com')
        password = config('ADMIN_PASSWORD', default='Admin@123456')
        username = email.split('@')[0]

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='مدير',
                last_name='النظام',
            )
            self.stdout.write(self.style.SUCCESS(
                f'✅ تم إنشاء المشرف: {email} / {password}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠️  المشرف موجود مسبقاً: {username}'
            ))
