from django.contrib.sessions.models import Session


def expire_user_sessions(user_id):
    deleted = 0

    for session in Session.objects.all():
        try:
            data = session.get_decoded()
        except Exception:
            continue

        if str(data.get("_auth_user_id")) == str(user_id):
            session.delete()
            deleted += 1

    return deleted
