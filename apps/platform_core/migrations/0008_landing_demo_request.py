from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("platform_core", "0007_subscriptionplan_tenantsubscription")]

    operations = [
        migrations.CreateModel(
            name="LandingDemoRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("company", models.CharField(blank=True, max_length=180)),
                ("phone", models.CharField(max_length=60)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("focus", models.CharField(blank=True, max_length=140)),
                ("message", models.TextField(blank=True)),
                ("source", models.CharField(default="landing", max_length=80)),
                ("status", models.CharField(choices=[("new", "جديد"), ("contacted", "تم التواصل"), ("qualified", "مهتم"), ("closed", "مغلق")], db_index=True, default="new", max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["status", "-created_at"], name="idx_landing_demo_status")],
            },
        ),
    ]
