from django.conf import settings
from django.core.exceptions import ValidationError


def validate_video_size(upload):
    limit = settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024
    if upload.size > limit:
        raise ValidationError(f"حجم ویدئو نباید بیشتر از {settings.MAX_VIDEO_UPLOAD_MB} مگابایت باشد.")


def validate_attachment_size(upload):
    limit = settings.MAX_SUBMISSION_MB * 1024 * 1024
    if upload.size > limit:
        raise ValidationError(f"حجم فایل نباید بیشتر از {settings.MAX_SUBMISSION_MB} مگابایت باشد.")
