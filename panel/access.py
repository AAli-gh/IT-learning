"""Who may see what in the student panel: only students with a *confirmed* enrollment."""

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from courses.models import Announcement, Course, Enrollment


def confirmed_enrollments(user):
    return Enrollment.objects.filter(user=user, status=Enrollment.Status.CONFIRMED)


def my_courses(user):
    ids = confirmed_enrollments(user).values_list("course_id", flat=True)
    return Course.objects.filter(pk__in=ids).select_related("category", "instructor")


def course_for_student(user, slug):
    """The course if the user is a confirmed student of it, else 404 (don't reveal that it exists)."""
    course = get_object_or_404(Course, slug=slug)
    if not confirmed_enrollments(user).filter(course=course).exists():
        raise Http404
    return course


def my_announcements(user):
    enrollments = confirmed_enrollments(user)
    course_ids = enrollments.values_list("course_id", flat=True)
    batch_ids = enrollments.exclude(batch=None).values_list("batch_id", flat=True)
    # A batch-specific notice only reaches students of that batch; course-wide notices reach all.
    own_batch = Q(batch__isnull=True) | Q(batch_id__in=batch_ids)
    return Announcement.objects.filter(is_published=True, course_id__in=course_ids).filter(own_batch).select_related("course")
