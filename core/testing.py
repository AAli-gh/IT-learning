"""Helpers shared by tests: keep uploaded private files in a throw-away directory."""

import shutil
import tempfile

from django.core.files.storage import FileSystemStorage


def use_temp_private_storage(testcase):
    from courses.models import Lesson, Submission

    root = tempfile.mkdtemp()
    testcase.addCleanup(shutil.rmtree, root, True)
    for field in (Lesson._meta.get_field("video_file"), Lesson._meta.get_field("attachment"),
                  Submission._meta.get_field("file")):
        old, field.storage = field.storage, FileSystemStorage(location=root)
        testcase.addCleanup(setattr, field, "storage", old)
    return root
