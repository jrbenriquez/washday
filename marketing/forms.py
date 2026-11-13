import uuid

from django import forms
from django.core import signing

from .models import Inquiry

TOKEN_SALT = "marketing.inquiry"


def submission_token():
    return signing.dumps(str(uuid.uuid4()), salt=TOKEN_SALT)


class InquiryForm(forms.ModelForm):
    type = forms.ChoiceField(
        choices=[(Inquiry.Type.DEMO, "Show me WashDay"), (Inquiry.Type.CUSTOM, "I have a question")],
        widget=forms.RadioSelect,
    )
    branch_count = forms.IntegerField(
        label="Number of branches (optional)", required=False, min_value=1, max_value=999,
    )
    submission_token = forms.CharField(widget=forms.HiddenInput)
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = Inquiry
        fields = ["type", "name", "email", "phone", "shop_name", "branch_count", "availability", "message"]
        labels = {
            "type": "How can we help?", "name": "Your name", "email": "Email address",
            "phone": "Phone number (optional)", "shop_name": "Shop name",
            "branch_count": "Number of branches (optional)",
            "availability": "Good days or times for a demo (optional)",
            "message": "What would you like us to know?",
        }
        widgets = {
            "type": forms.RadioSelect,
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "type": "tel"}),
            "shop_name": forms.TextInput(attrs={"autocomplete": "organization"}),
            "branch_count": forms.NumberInput(attrs={"min": 1, "max": 999}),
            "availability": forms.TextInput(attrs={"placeholder": "e.g. Weekday afternoons, Philippine time"}),
            "message": forms.Textarea(attrs={"rows": 4, "maxlength": 4000}),
        }

    def __init__(self, *args, **kwargs):
        if args and args[0] is not None and args[0].get("type") == Inquiry.Type.CUSTOM:
            data = args[0].copy()
            data["branch_count"] = ""
            data["availability"] = ""
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ("type", "submission_token", "website"):
                field.widget.attrs["aria-describedby"] = f"id_{name}_help id_{name}_errors"
            if self.is_bound and name in self.errors:
                field.widget.attrs["aria-invalid"] = "true"

    def clean_submission_token(self):
        try:
            value = signing.loads(self.cleaned_data["submission_token"], salt=TOKEN_SALT, max_age=7200)
            self.submission_id = uuid.UUID(value)
        except (signing.BadSignature, ValueError, TypeError):
            raise forms.ValidationError("This form expired. Please reload the page and try again.")
        return self.cleaned_data["submission_token"]

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("We couldn’t save this request. Please reload and try again.")
        if data.get("type") == Inquiry.Type.DEMO and not data.get("shop_name"):
            self.add_error("shop_name", "Tell us your shop name so we can tailor the demo.")
        if data.get("type") == Inquiry.Type.CUSTOM and not data.get("message"):
            self.add_error("message", "Tell us a little about your question.")
        return data
