from django import forms


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
