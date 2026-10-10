from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.home, name="home"),
    path("courses/", views.course_list, name="list"),
    path("courses/category/<str:category>/", views.course_list, name="category"),
    path("courses/<str:slug>/", views.course_detail, name="detail"),
    path("courses/<str:slug>/enroll/", views.enroll, name="enroll"),
]
