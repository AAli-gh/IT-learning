from django import forms

from courses.forms import _FA_TO_EN, PHONE_RE

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "hp-field", "tabindex": "-1", "autocomplete": "off"}))  # honeypot

    class Meta:
        model = ContactMessage
        fields = ("name", "phone", "email", "subject", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("spam")
        return ""

    def clean_phone(self):
        phone = self.cleaned_data["phone"].translate(_FA_TO_EN).replace(" ", "").replace("-", "")
        if phone and not PHONE_RE.match(phone):
            raise forms.ValidationError("شماره موبایل معتبر وارد کنید.")
        return phone

    def clean(self):
        data = super().clean()
        if not data.get("phone") and not data.get("email"):
            raise forms.ValidationError("برای پاسخ‌گویی، شماره تماس یا ایمیل را وارد کنید.")
        return data
