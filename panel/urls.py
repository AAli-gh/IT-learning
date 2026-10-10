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
    path("courses/<str:slug>/quizzes/<int:pk>/", views.quiz_detail, name="quiz"),
    path("courses/<str:slug>/quizzes/<int:pk>/start/", views.quiz_start, name="quiz_start"),
    path("courses/<str:slug>/quizzes/<int:pk>/attempt/<int:attempt_id>/", views.quiz_attempt, name="quiz_attempt"),
    path("courses/<str:slug>/quizzes/<int:pk>/result/<int:attempt_id>/", views.quiz_result, name="quiz_result"),
    path("courses/<str:slug>/assignments/<int:pk>/", views.assignment_detail, name="assignment"),
    path("submissions/<int:pk>/file/", views.submission_file, name="submission_file"),
    path("courses/<str:slug>/certificate/", views.certificate_issue, name="certificate_issue"),
    path("certificates/", views.certificates, name="certificates"),
    path("schedule/", views.schedule, name="schedule"),
    path("announcements/", views.announcements, name="announcements"),
    path("enrollments/", views.enrollments, name="enrollments"),
    path("enrollments/<int:pk>/cancel/", views.cancel_enrollment, name="cancel_enrollment"),
]
