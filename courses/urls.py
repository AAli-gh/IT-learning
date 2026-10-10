from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.home, name="home"),
    path("courses/", views.course_list, name="list"),
    path("courses/suggest/", views.suggest, name="suggest"),
    path("courses/category/<str:category>/", views.course_list, name="category"),
    path("courses/<str:slug>/", views.course_detail, name="detail"),
    path("courses/<str:slug>/enroll/", views.enroll, name="enroll"),
    path("courses/<str:slug>/review/", views.review, name="review"),
    path("certificates/<str:code>/", views.certificate, name="certificate"),
    path("instructors/", views.instructors, name="instructors"),
    path("faq/", views.faq, name="faq"),
]
