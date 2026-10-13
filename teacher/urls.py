from django.urls import path

from . import views

app_name = "teacher"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("<str:slug>/", views.course_home, name="course"),
    path("<str:slug>/lessons/", views.lessons, name="lessons"),
    path("<str:slug>/lessons/new/", views.lesson_edit, name="lesson_new"),
    path("<str:slug>/lessons/<int:pk>/", views.lesson_edit, name="lesson_edit"),
    path("<str:slug>/lessons/<int:pk>/delete/", views.lesson_delete, name="lesson_delete"),
    path("<str:slug>/announcements/", views.announcements, name="announcements"),
    path("<str:slug>/announcements/<int:pk>/delete/", views.announcement_delete, name="announcement_delete"),
    path("<str:slug>/assignments/", views.assignments, name="assignments"),
    path("<str:slug>/assignments/new/", views.assignment_edit, name="assignment_new"),
    path("<str:slug>/assignments/<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
    path("<str:slug>/assignments/<int:pk>/", views.assignment, name="assignment"),
    path("<str:slug>/assignments/<int:pk>/grade/<int:submission_id>/", views.grade, name="grade"),
    path("<str:slug>/sessions/", views.sessions, name="sessions"),
    path("<str:slug>/sessions/new/", views.session_edit, name="session_new"),
    path("<str:slug>/sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("<str:slug>/sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("<str:slug>/sessions/<int:pk>/attendance/", views.attendance, name="attendance"),
    path("<str:slug>/students/", views.students, name="students"),
    path("<str:slug>/students/<int:user_id>/", views.student_detail, name="student"),
]
