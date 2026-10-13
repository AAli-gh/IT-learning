from django.db import migrations

from core.textutils import normalize


def backfill(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    Enrollment = apps.get_model("courses", "Enrollment")
    for course in Course.objects.select_related("category"):
        parts = [course.title, course.summary, course.description, course.magazine_tag, course.prerequisites,
                 course.category.name]
        course.search_text = normalize(" ".join(p for p in parts if p))
        course.save(update_fields=["search_text"])
    # Existing enrollments were registered at the course's current fee.
    for enrollment in Enrollment.objects.filter(price=0).select_related("course"):
        enrollment.price = enrollment.course.price
        enrollment.save(update_fields=["price"])


class Migration(migrations.Migration):
    dependencies = [("courses", "0005_classsession_reminded_at_course_search_text_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
