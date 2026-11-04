from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django import forms
from .models import DriveBackup


class ScheduleForm(forms.ModelForm):
    every_days = forms.IntegerField(
        min_value=1,
        max_value=365,
        label="Repeat every (days)",
        help_text="1 = daily, 7 = weekly. Starts at the next occurrence of the selected time.",
    )

    class Meta:
        model = DriveBackup
        fields = ["enabled", "every_days", "local_time", "timezone"]
        labels = {
            "enabled": "Enable automatic exports",
            "local_time": "Export time",
            "timezone": "Timezone",
        }
        widgets = {
            "local_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"})
        }

    def clean_timezone(self):
        value = self.cleaned_data["timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError(
                "Enter an IANA timezone, for example Asia/Manila."
            )
        return value

    def clean(self):
        data = super().clean()
        if data.get("enabled") and (
            not self.instance.folder_id or not self.instance.refresh_token_encrypted
        ):
            raise forms.ValidationError(
                "Connect Drive and select a destination folder first."
            )
        return data


class FolderForm(forms.Form):
    folder_id = forms.RegexField(
        r"^[A-Za-z0-9_-]{1,200}$", required=False, max_length=200
    )
    new_name = forms.CharField(required=False, max_length=200)

    def clean(self):
        data = super().clean()
        if bool(data.get("folder_id")) == bool(data.get("new_name")):
            raise forms.ValidationError(
                "Select a folder or enter a name to create one."
            )
        return data
