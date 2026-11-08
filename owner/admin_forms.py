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
                    (
                        "Enter a positive value."
                        if field != "min_kg"
                        else "Enter zero or more."
                    ),
                )
        return data


class EditorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "show_in_simple_mode" and isinstance(self.instance, JobStage):
                if self.instance.is_first or self.instance.is_last:
                    field.disabled = True
                    field.initial = True
                    self.initial[name] = True
                    field.help_text = "Always shown. The first and last stages are always visible in simple mode."
                else:
                    field.help_text = "Show this middle stage on the simple-mode board."
            if name == "move_on_when_unloaded":
                field.help_text = "In full mode, automatically move the job to the next stage when staff unload its last active machine load. The next stage must not require a machine."
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
        if (
            isinstance(self.instance, PieceVariant)
            and data.get("piece_item")
            and data.get("label")
        ):
            if (
                PieceVariant.objects.filter(
                    piece_item=data["piece_item"], label__iexact=data["label"]
                )
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                self.add_error(
                    "label", "This size already exists. Restore it if removed."
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


class BranchForm(forms.ModelForm):
    connection_mode = forms.ChoiceField(
        label="Connection mode",
        choices=[("direct", "Direct"), ("hub", "Hub")],
        disabled=True,
        help_text="Connection changes will be available after safe hub migration is supported.",
    )

    class Meta:
        from core.models import Branch

        model = Branch
        fields = ["name", "code", "opening_time", "closing_time", "simple_mode"]
        labels = {"simple_mode": "Use simple workflow"}
        help_texts = {
            "code": "A unique code for this branch within your shop.",
            "simple_mode": "Show the simplified job board and hide machine tracking. Clear for full workflow.",
            "closing_time": "New personal shifts end at the next closing time.",
        }
        widgets = {
            "opening_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "closing_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connection_mode"].initial = self.instance.mode

    def clean_code(self):
        from core.models import Branch

        code = self.cleaned_data["code"]
        if (
            Branch.objects.filter(code__iexact=code)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError(
                "A branch with this code already exists in your shop."
            )
        return code

    def clean(self):
        data = super().clean()
        # Reject forged mode fields as well as leaving the displayed mode read-only.
        for key in ("mode", "connection_mode"):
            if key in self.data and self.data[key] != self.instance.mode:
                self.add_error(
                    "connection_mode", "Connection changes are not available yet."
                )
        if data.get("simple_mode") and not self.instance._state.adding:
            from machines.models import Load

            if (
                not self.instance.simple_mode
                and Load.objects.filter(branch=self.instance, ended_at=None).exists()
            ):
                self.add_error(
                    "simple_mode",
                    "Unload running machines before switching to simple mode.",
                )
        return data


class NewPieceForm(EditorForm):
    label = forms.CharField(label="Size (optional)", max_length=80, required=False)
    price = forms.DecimalField(
        label="Price (₱)", max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = PieceItem
        fields = ["name"]

    def clean_name(self):
        name = self.cleaned_data["name"]
        if PieceItem.objects.filter(name__iexact=name).exists():
            raise ValidationError(
                "This piece item already exists. Restore it if archived."
            )
        return name

    def save(self, commit=True):
        item = super().save(commit=commit)
        if commit:
            PieceVariant.objects.create(
                shop_id=item.shop_id,
                piece_item=item,
                label=self.cleaned_data["label"] or "Each",
                price=self.cleaned_data["price"],
            )
        return item
