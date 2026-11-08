from django import forms
from core.models import Shop


class ShopBrandingForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ["name", "logo"]
        labels = {"name": "Shop name", "logo": "Shop logo"}
        widgets = {
            "logo": forms.ClearableFileInput(
                attrs={"accept": "image/png,image/jpeg,image/webp"}
            )
        }
        help_texts = {
            "logo": "PNG, JPEG or WebP, up to 2 MB. Leave empty to use the WashDay icon."
        }

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "image"):
            if logo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Choose a logo smaller than 2 MB.")
            if logo.image.format not in ("PNG", "JPEG", "WEBP"):
                raise forms.ValidationError("Choose a PNG, JPEG or WebP image.")
        return logo


class StaffForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "staff_%s")
        super().__init__(*args, **kwargs)

    name = forms.CharField(max_length=120, label="Staff name")
    pin = forms.RegexField(
        regex=r"^[0-9]{4}$",
        required=False,
        label="Four-digit PIN (leave blank to generate)",
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "inputmode": "numeric",
                "maxlength": 4,
                "autocomplete": "new-password",
            },
        ),
    )


class DeviceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "device_%s")
        super().__init__(*args, **kwargs)

    name = forms.CharField(max_length=120, label="Device name")
    kind = forms.ChoiceField(
        choices=[
            ("shared", "Shared counter tablet"),
            ("personal", "Personal staff phone"),
        ],
        label="Device type",
    )


class HoursForm(forms.Form):
    opening_time = forms.TimeField(
        label="Opening time",
        help_text="Job creation and updates require operating hours. Matching times mean open 24 hours.",
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    closing_time = forms.TimeField(
        label="Closing time",
        help_text="Job writes stop at closing. Overnight hours are supported (Asia/Manila).",
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )


PIN_CHOICES = [
    ("payment", "Collecting payment (including intake and self-service)"),
    ("claim", "Claiming a job"),
    ("override", "Manually correcting a stage"),
    ("create", "Creating any job"),
    ("count", "Saving a stock count"),
    ("receive", "Receiving stock"),
    ("add_type", "Adding a supply type"),
]


class PolicyForm(forms.Form):
    pin_enabled = forms.BooleanField(
        required=False, label="Require PINs on shared devices"
    )
    pin_actions = forms.MultipleChoiceField(
        choices=PIN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Ask for a PIN when",
    )
