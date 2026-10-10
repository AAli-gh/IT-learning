from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import Course, Enrollment

from .forms import ProfileForm
from .models import User


@login_required
def profile(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related("course", "batch")
    return render(request, "accounts/profile.html", {"enrollments": enrollments})


@login_required
def edit_profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "پروفایل ذخیره شد.")
        return redirect("accounts:profile")
    return render(request, "accounts/edit_profile.html", {"form": form})


def instructor(request, username):
    person = get_object_or_404(User, username=username, is_instructor=True)
    courses = Course.objects.published().filter(instructor=person)
    return render(request, "accounts/instructor.html", {"person": person, "courses": courses})
