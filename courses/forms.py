import re

from django import forms

from .models import Batch, Enrollment, Review

PHONE_RE = re.compile(r"^(\+98|0098|0)?9\d{9}$")
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class EnrollmentForm(forms.ModelForm):
    # Honeypot: real users never see or fill this field.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "hp-field", "tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = Enrollment
        fields = ("full_name", "phone", "email", "batch", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        self.fields["batch"].queryset = course.batches.filter(is_open=True)
        self.fields["batch"].required = False
        self.fields["batch"].label_from_instance = lambda b: (
            f"{b.title or b.start_date} ({b.get_mode_display()})"
            + ("" if b.accepts_enrollment else " — تکمیل ظرفیت؛ ثبت در لیست انتظار"))
        self.fields["batch"].empty_label = "هنوز مطمئن نیستم / فعلاً مشاوره می‌خواهم"
        self.fields["email"].required = False

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("spam")
        return ""

    def clean_phone(self):
        phone = self.cleaned_data["phone"].translate(_FA_TO_EN).replace(" ", "").replace("-", "")
        if not PHONE_RE.match(phone):
            raise forms.ValidationError("شماره موبایل معتبر وارد کنید (مثلاً ۰۹۱۲۱۲۳۴۵۶۷).")
        return phone



class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "text")
        widgets = {"text": forms.Textarea(attrs={"rows": 3}), "rating": forms.RadioSelect}
