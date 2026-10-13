"""Instructors manage only their own courses; superusers manage all. Anything else is a 404 (no hint it exists)."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404

from courses.models import Course


def instructor_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_instructor or request.user.is_superuser):
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


def teaching_courses(user):
    courses = Course.objects.select_related("category")
    return courses if user.is_superuser else courses.filter(instructor=user)


def teacher_course(user, slug):
    return get_object_or_404(teaching_courses(user), slug=slug)
