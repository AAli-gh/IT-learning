from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    """Lesson files live outside MEDIA_ROOT and are only served by panel.views.lesson_file after an access check.

    A callable (not an instance) so migrations don't capture this machine's absolute path.
    """
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)
