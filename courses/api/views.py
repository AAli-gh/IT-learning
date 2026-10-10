from rest_framework import viewsets

from courses.models import Category, Course

from .serializers import CategorySerializer, CourseDetailSerializer, CourseListSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"
    pagination_class = None


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Published courses. Filters: ``?q=``, ``?category=``, ``?level=``, ``?tag=`` (magazine tag)."""

    lookup_field = "slug"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        params = self.request.query_params
        qs = Course.objects.published().with_relations().prefetch_related("topics")
        qs = qs.search(params.get("q", "").strip())
        if params.get("category"):
            qs = qs.filter(category__slug=params["category"])
        if params.get("level"):
            qs = qs.filter(level=params["level"])
        if params.get("tag"):
            qs = qs.filter(magazine_tag=params["tag"])
        return qs

    def get_serializer_class(self):
        return CourseDetailSerializer if self.action == "retrieve" else CourseListSerializer
