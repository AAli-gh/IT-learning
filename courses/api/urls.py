from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, CourseViewSet

router = DefaultRouter()
router.register("courses", CourseViewSet, basename="course")
router.register("categories", CategoryViewSet)

urlpatterns = router.urls
