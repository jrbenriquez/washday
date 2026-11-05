from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from catalog.models import SupplyType
from catalog.supply_identity import merge

from .views import owner


class MergeForm(forms.Form):
    target = forms.ModelChoiceField(
        queryset=SupplyType.objects.none(), label="Surviving supply type"
    )
    settings_from = forms.ChoiceField(
        choices=[
            ("target", "Keep survivor settings"),
            ("source", "Use the duplicate settings"),
        ],
        label="Settings to keep",
    )

    def __init__(self, source, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = SupplyType.objects.filter(
            archived_at=None
        ).exclude(pk=source.pk)
        self.fields["target"].label_from_instance = lambda obj: (
            f"{obj.name} · {obj.unit} · low {obj.low_level:g}, washer {obj.per_washer_load:g}, packed {obj.per_packed_job:g}"
        )


@require_http_methods(["GET", "POST"])
def edit(request, source_id):
    owner(request)
    source = get_object_or_404(SupplyType, pk=source_id, archived_at=None)
    form = MergeForm(source, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            merge(
                source, form.cleaned_data["target"], form.cleaned_data["settings_from"]
            )
            messages.success(
                request,
                "Supply types merged. Both histories and all stock movements are retained.",
            )
            return redirect("owner_dashboard")
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "owner/editor.html",
        {
            "form": form,
            "heading": "Merge " + source.name,
            "back": "owner_dashboard",
            "intro": f"Duplicate: {source.name} · {source.unit}; low {source.low_level:g}, per washer {source.per_washer_load:g}, per packed job {source.per_packed_job:g}. Both histories are retained. Units must match.",
        },
        status=422 if form.errors else 200,
    )
