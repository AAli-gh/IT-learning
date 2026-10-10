from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("courses/", views.courses, name="courses"),
    path("courses/<str:slug>/", views.course_home, name="course"),
    path("courses/<str:slug>/lessons/<int:pk>/", views.lesson, name="lesson"),
    path("courses/<str:slug>/lessons/<int:pk>/done/", views.toggle_lesson, name="toggle_lesson"),
    path("courses/<str:slug>/lessons/<int:pk>/file/", views.lesson_file, name="lesson_file"),
    path("schedule/", views.schedule, name="schedule"),
    path("announcements/", views.announcements, name="announcements"),
    path("enrollments/", views.enrollments, name="enrollments"),
    path("enrollments/<int:pk>/cancel/", views.cancel_enrollment, name="cancel_enrollment"),
]
