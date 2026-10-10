from rest_framework import serializers

from courses.models import Batch, Category, Course, Topic


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "description"]


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["title", "order"]


class BatchSerializer(serializers.ModelSerializer):
    seats_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batch
        fields = ["title", "start_date", "schedule", "mode", "capacity", "seats_left", "is_open"]


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    instructor = serializers.CharField(source="instructor.display_name", default=None, read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "slug", "url", "category", "level", "summary", "cover", "price",
            "duration_hours", "instructor", "magazine_tag", "published_at",
        ]

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.get_absolute_url()
        return request.build_absolute_uri(url) if request else url


class CourseDetailSerializer(CourseListSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    batches = BatchSerializer(many=True, read_only=True)

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + [
            "description", "description_html", "prerequisites", "topics", "batches", "updated_at"]
