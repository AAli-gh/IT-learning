from .models import Notification


def unread(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {"unread_notifications": Notification.objects.filter(user=user, is_read=False).count()}
    return {"unread_notifications": 0}
