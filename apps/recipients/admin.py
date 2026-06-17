from django.contrib import admin
from .models import MailingList, Recipient, UnsubscribeList, UploadBatch
admin.site.register(MailingList)
admin.site.register(Recipient)
admin.site.register(UnsubscribeList)
admin.site.register(UploadBatch)
