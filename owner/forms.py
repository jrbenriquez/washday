from django import forms
from core.models import Shop
from people.models import Staff


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


class StaffChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} · {obj.branch.name}"


class DeviceAssignmentForm(forms.Form):
    assigned_staff = StaffChoiceField(
        queryset=Staff.objects.none(), required=True, label="Assigned staff",
    )

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_staff"].queryset = Staff.objects.filter(
            active=True, **({"branch": branch} if branch else {})
        ).select_related("branch").order_by("branch__name", "name")


class DeviceForm(DeviceAssignmentForm):
    field_order = ["name", "kind", "assigned_staff"]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "device_%s")
        super().__init__(*args, **kwargs)
        self.fields["assigned_staff"].required = False

    def clean(self):
        data = super().clean()
        staff = data.get("assigned_staff")
        if data.get("kind") == "personal" and not staff:
            self.add_error("assigned_staff", "Choose the staff member who owns this phone.")
        if data.get("kind") == "shared":
            data["assigned_staff"] = None
        return data

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
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    closing_time = forms.TimeField(
        label="Closing time",
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
