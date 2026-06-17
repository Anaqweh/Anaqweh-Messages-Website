# 📧 INEXC Email Campaign Manager

نظام إدارة الحملات البريدية الداخلي لـ INEXC — مبني بـ Django + Celery + Redis + EmailJS

---

## 🚀 التشغيل السريع

### 1. استنساخ المشروع وإعداد البيئة

```bash
git clone <repo-url>
cd inexc_email

cp .env.example .env
# عدّل .env وضع بيانات EmailJS وقاعدة البيانات
```

### 2. أضف بيانات EmailJS في ملف .env

```env
EMAILJS_SERVICE_ID=your_service_id
EMAILJS_TEMPLATE_ID=your_template_id
EMAILJS_PUBLIC_KEY=your_public_key
EMAILJS_PRIVATE_KEY=your_private_key
```

> احصل عليها من: https://www.emailjs.com/docs/rest-api/send/

### 3. تشغيل بـ Docker (الأسرع)

```bash
docker compose up --build
```

ثم افتح: **http://localhost:8000**

بيانات الدخول الافتراضية:
- **المستخدم:** `admin`
- **كلمة المرور:** `Admin@123456`

---

## 🛠 تشغيل محلي (بدون Docker)

### المتطلبات
- Python 3.11+
- PostgreSQL
- Redis

```bash
# إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# تثبيت المكتبات
pip install -r requirements.txt

# إعداد قاعدة البيانات
python manage.py migrate

# إنشاء المشرف
python manage.py create_admin

# تحميل بيانات تجريبية
python manage.py load_demo_data

# جمع الملفات الثابتة
python manage.py collectstatic --no-input

# تشغيل الخادم
python manage.py runserver
```

في نوافذ منفصلة:

```bash
# Celery Worker
celery -A config worker --loglevel=info

# Celery Beat (للمهام المجدولة)
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## 📁 هيكل المشروع

```
inexc_email/
├── config/
│   ├── settings.py       # إعدادات Django
│   ├── celery.py         # إعداد Celery
│   └── urls.py           # URLs الرئيسية
├── apps/
│   ├── accounts/         # تسجيل الدخول والمشرفون
│   ├── campaigns/        # الحملات + EmailJS + Celery Tasks
│   ├── recipients/       # القوائم + رفع الملفات
│   ├── templates_mgr/    # القوالب البريدية
│   └── reports/          # التقارير + التصدير
├── templates/            # HTML Templates (Django)
├── static/               # CSS / JS / Images
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## ✉️ إعداد EmailJS

### خطوات ربط EmailJS:

1. سجل في [emailjs.com](https://www.emailjs.com)
2. أضف **Email Service** (Gmail, Outlook, SMTP…)
3. أنشئ **Email Template** بهذه المتغيرات:
   ```
   To:       {{to_email}}
   Subject:  {{subject}}
   Body:     {{body_html}}
   ```
4. انسخ:
   - `Service ID` → `EMAILJS_SERVICE_ID`
   - `Template ID` → `EMAILJS_TEMPLATE_ID`
   - `Public Key` → `EMAILJS_PUBLIC_KEY`
   - `Private Key` → `EMAILJS_PRIVATE_KEY`
5. أضفها في `.env`

---

## 🔑 متغيرات البيئة الرئيسية

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `SECRET_KEY` | مفتاح Django | يجب تغييره |
| `DEBUG` | وضع التطوير | `True` |
| `DB_NAME` | اسم قاعدة البيانات | `inexc_email` |
| `EMAILJS_SERVICE_ID` | معرف خدمة EmailJS | — |
| `EMAILJS_TEMPLATE_ID` | معرف قالب EmailJS | — |
| `EMAILJS_PUBLIC_KEY` | المفتاح العام | — |
| `EMAILJS_PRIVATE_KEY` | المفتاح الخاص | — |
| `BATCH_SIZE` | حجم دفعة الإرسال | `50` |
| `BATCH_DELAY_SECONDS` | تأخير بين الدفعات | `2` |
| `MAX_RETRIES` | أقصى محاولات إعادة | `3` |
| `ADMIN_EMAIL` | بريد المشرف | `admin@inexc.com` |
| `ADMIN_PASSWORD` | كلمة مرور المشرف | `Admin@123456` |

---

## 📊 ميزات النظام

| الميزة | الوصف |
|--------|-------|
| ✅ لوحة تحكم | إحصائيات فورية + آخر العمليات |
| ✅ إدارة القوالب | HTML كامل + متغيرات ديناميكية + معاينة |
| ✅ رفع الملفات | Excel, CSV, TSV مع كشف تلقائي لعمود الإيميل |
| ✅ الحملات | فوري + مجدول + إيقاف + استئناف + إلغاء |
| ✅ Celery + Redis | إرسال في الخلفية، دفعات، إعادة محاولة |
| ✅ EmailJS | REST API، لا SMTP مطلوب |
| ✅ التقارير | نسبة النجاح، تصدير CSV/Excel |
| ✅ إلغاء الاشتراك | لينك في كل رسالة، قائمة محظورة |
| ✅ رسالة اختبارية | اختبار القالب قبل الإطلاق |
| ✅ تتبع كامل | وقت الإرسال، المحاولات، سبب الفشل |

---

## 🐳 أوامر Docker مفيدة

```bash
# تشغيل كامل
docker compose up -d

# مشاهدة اللوجات
docker compose logs -f app
docker compose logs -f celery_worker

# إعادة البناء
docker compose up --build

# إيقاف كامل
docker compose down

# حذف كل شيء (بيانات مشمولة)
docker compose down -v
```

---

## 🔄 دورة حياة الحملة

```
مسودة (draft)
    ↓
تشغيل → run_campaign_task (Celery)
    ↓
إنشاء EmailLog لكل مستلم
    ↓
send_single_email_task × N (دفعات)
    ↓
EmailJS REST API → sent / failed
    ↓
إعادة محاولة تلقائية (Max 3)
    ↓
مكتملة (completed)
```

---

## 📞 الدعم

للاستفسارات: info@inexc.com
