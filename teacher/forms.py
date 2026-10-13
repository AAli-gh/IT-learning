from django import forms

from courses.models import Announcement, Assignment, ClassSession, Lesson

_DT = {"format": "%Y-%m-%dT%H:%M", "input_formats": ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]}


def _dt_widget():
    return forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ("title", "order", "body", "video_file", "video_url", "attachment", "duration_minutes", "is_published")
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "body", "batch", "is_published")
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = course.batches.all()
        self.fields["batch"].empty_label = "همهٔ دانشجویان دوره"


class AssignmentForm(forms.ModelForm):
    due_at = forms.DateTimeField(required=False, label="مهلت تحویل", widget=_dt_widget(),
                                 input_formats=_DT["input_formats"])

    class Meta:
        model = Assignment
        fields = ("title", "description", "order", "due_at", "allow_late", "max_score", "pass_percent", "is_published")
        widgets = {"description": forms.Textarea(attrs={"rows": 8})}


class SessionForm(forms.ModelForm):
    starts_at = forms.DateTimeField(label="زمان شروع", widget=_dt_widget(), input_formats=_DT["input_formats"])

    class Meta:
        model = ClassSession
        fields = ("batch", "title", "starts_at", "duration_minutes", "place", "recording_url")

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = course.batches.all()  # only batches of this course


class GradeForm(forms.Form):
    score = forms.IntegerField(label="نمره", min_value=0)
    feedback = forms.CharField(label="بازخورد", required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment

    def clean_score(self):
        score = self.cleaned_data["score"]
        if score > self.assignment.max_score:
            raise forms.ValidationError(f"نمره نمی‌تواند بیشتر از {self.assignment.max_score} باشد.")
        return score
