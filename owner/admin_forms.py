"""Owner editors use the same tenant-scoped models as counter operations."""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from catalog.models import (
    AddOn,
    AddOnUse,
    Fee,
    PieceItem,
    PieceVariant,
    Service,
    SupplyType,
)
from core.models import JobStage, Machine, MachineCategory, Settings


class OperationsForm(forms.ModelForm):
    class Meta:
        model = Settings
        fields = ["min_kg", "kg_per_load", "check_after_min", "staff_can_add_supply"]
        labels = {
            "min_kg": "Minimum kilos",
            "kg_per_load": "Kilos per load",
            "check_after_min": "Flag a machine to check after (minutes)",
            "staff_can_add_supply": "Let staff add supply types",
        }

    def clean(self):
        data = super().clean()
        for field in ("min_kg", "kg_per_load", "check_after_min"):
            value = data.get(field)
            if value is not None and (value < 0 or (field != "min_kg" and value == 0)):
                self.add_error(
                    field,
                    "Enter a positive value."
                    if field != "min_kg"
                    else "Enter zero or more.",
                )
        return data


class EditorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "sort_order" and isinstance(self.instance, JobStage):
                field.help_text = "Position on the board. Other stages shift automatically; the first and Ready stages stay at the ends."
            if name == "machine_category":
                field.required = False
            if isinstance(field, forms.DecimalField):
                field.min_value = Decimal("0")
                field.widget.attrs["min"] = "0"
            if isinstance(field, forms.ModelChoiceField):
                qs = field.queryset
                if "archived_at" in [f.name for f in qs.model._meta.fields]:
                    field.queryset = qs.filter(archived_at=None)
                field.label_from_instance = lambda obj: obj.name
            if name in ("price", "amount", "qty"):
                field.label = {
                    "price": "Price (₱)",
                    "amount": "Amount (₱)",
                    "qty": "Quantity used per job",
                }[name]

    def clean(self):
        data = super().clean()
        for name, field in self.fields.items():
            if (
                isinstance(field, forms.DecimalField)
                and data.get(name) is not None
                and data[name] < 0
            ):
                self.add_error(name, "Enter zero or more.")
        if (
            isinstance(self.instance, Machine)
            and self.instance.pk
            and not self.instance._state.adding
        ):
            from machines.models import Load

            if Load.objects.filter(machine=self.instance, ended_at=None).exists():
                if any(
                    name in self.changed_data
                    for name in ("branch", "category", "out_of_service")
                ):
                    raise ValidationError(
                        "Unload this machine before changing its branch, category or service status."
                    )
        if isinstance(self.instance, JobStage):
            category = data.get("machine_category")
            if data.get("ask_for_machine") and not category:
                self.add_error(
                    "machine_category", "Choose a category for a machine stage."
                )
            if data.get("move_on_when_unloaded") and not data.get("ask_for_machine"):
                self.add_error(
                    "move_on_when_unloaded", "Auto-next requires a machine stage."
                )
            if self.instance.is_first or self.instance.is_last:
                if data.get("ask_for_machine"):
                    self.add_error(
                        "ask_for_machine",
                        "The first and Ready stages cannot require machines.",
                    )
            active = JobStage.objects.filter(archived_at=None).exclude(
                pk=self.instance.pk
            )
            order = data.get("sort_order")
            if order is not None:
                first, last = (
                    active.filter(is_first=True).first(),
                    active.filter(is_last=True).first(),
                )
                if (first and order <= first.sort_order) or (
                    last and order > last.sort_order
                ):
                    self.add_error(
                        "sort_order", "Keep stages between the first and Ready stages."
                    )
                if (
                    self.instance.is_first
                    and active.filter(sort_order__lte=order).exists()
                ):
                    self.add_error("sort_order", "The first stage must stay first.")
                if (
                    self.instance.is_last
                    and active.filter(sort_order__gte=order).exists()
                ):
                    self.add_error("sort_order", "Ready must stay last.")
            if self.instance.pk and not self.instance._state.adding:
                from machines.models import Load

                if (
                    Load.objects.filter(stage=self.instance, ended_at=None).exists()
                    and self.changed_data
                ):
                    raise ValidationError(
                        "Unload this stage's machines before editing it."
                    )
        if isinstance(self.instance, AddOnUse) and data.get("qty") == 0:
            self.add_error("qty", "Enter a quantity greater than zero.")
        return data


EDITORS = {
    "service": (Service, ["name", "mode", "price"], "Services"),
    "fee": (Fee, ["name", "note", "amount"], "Fees"),
    "addon": (AddOn, ["name", "price"], "Add-ons"),
    "supply": (
        SupplyType,
        ["name", "unit", "low_level", "per_washer_load", "per_packed_job"],
        "Supply types",
    ),
    "piece": (PieceItem, ["name"], "Piece items"),
    "size": (PieceVariant, ["piece_item", "label", "price"], "Piece sizes"),
    "recipe": (AddOnUse, ["addon", "supply_type", "qty"], "Add-on supply recipes"),
    "category": (
        MachineCategory,
        ["name", "label_prefix", "uses_wash_supplies", "sort_order"],
        "Machine categories",
    ),
    "machine": (Machine, ["branch", "label", "category", "out_of_service"], "Machines"),
    "stage": (
        JobStage,
        [
            "name",
            "sort_order",
            "ask_for_machine",
            "machine_category",
            "move_on_when_unloaded",
            "show_in_simple_mode",
        ],
        "Job stages",
    ),
}


def editor_form(kind):
    model, fields, _ = EDITORS[kind]
    return forms.modelform_factory(model, form=EditorForm, fields=fields)
