from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("page/<str:slug>/", views.page_detail, name="page"),
    path("errors/<int:code>/", views.error_preview, name="error_preview"),
]
