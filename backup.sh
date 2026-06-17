#!/bin/bash
# نسخة احتياطية لقاعدة البيانات
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T db pg_dump -U postgres inexc_email > backups/backup_$DATE.sql
# احتفظ بآخر 7 نسخ فقط
ls -t backups/backup_*.sql | tail -n +8 | xargs -r rm
echo "✅ Backup created: backups/backup_$DATE.sql"
ls -lh backups/ | tail -5
