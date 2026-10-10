from django.urls import path

from . import views

app_name = "accounts"

# Signup, login, logout, password reset, email verification and social login
# are provided by django-allauth (see config/urls.py).
urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("instructor/<str:username>/", views.instructor, name="instructor"),
]
