"""First owner setup writes the same catalog used by every branch."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.forms import BaseFormSet, formset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from catalog.models import PieceItem, PieceVariant, Service
from core.models import Branch, Settings, Shop
from people.services import audit
from .views import owner
from .admin_forms import BranchForm


class ServiceForm(forms.Form):
    record = forms.UUIDField(required=False, widget=forms.HiddenInput)
    name = forms.CharField(max_length=120, label="Service name")
    mode = forms.ChoiceField(choices=Service._meta.get_field("mode").choices, label="Bill by")
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, label="Price (₱)")


class PieceForm(forms.Form):
    record = forms.UUIDField(required=False, widget=forms.HiddenInput)
    name = forms.CharField(max_length=120, label="Piece item name")
    label = forms.CharField(max_length=80, initial="Each", label="Size / unit")
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, label="Price per piece (₱)")


class CatalogFormSet(BaseFormSet):
    def __init__(self, *args, records, **kwargs):
        self.records = {obj.pk: obj for obj in records}
        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Remove this item"

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen_records, seen_names = set(), set()
        for form in self.forms:
            data = form.cleaned_data
            record = data.get("record")
            if record:
                if record not in self.records or record in seen_records:
                    raise ValidationError("An item is invalid. Reload setup and try again.")
                seen_records.add(record)
            if not data or data.get("DELETE"):
                continue
            key = (data["name"].casefold(), data.get("label", "").casefold())
            if key in seen_names:
                raise ValidationError("Each item must have a different name or size.")
            seen_names.add(key)
        if seen_records != set(self.records):
            raise ValidationError("An item is missing. Reload setup and try again.")


Services = formset_factory(ServiceForm, formset=CatalogFormSet, extra=0, can_delete=True,
                           min_num=1, validate_min=True, max_num=100, validate_max=True)
Pieces = formset_factory(PieceForm, formset=CatalogFormSet, extra=0, can_delete=True,
                         max_num=100, validate_max=True)


class LimitsForm(forms.Form):
    min_kg = forms.DecimalField(max_digits=6, decimal_places=1, min_value=0,
                               label="Minimum kilos allowed",
                               help_text="Clothes below this weight are billed at the minimum weight.")
    kg_per_load = forms.DecimalField(max_digits=6, decimal_places=1, min_value=Decimal("0.1"),
                                    label="Maximum kilos per load")


@require_http_methods(["GET", "POST"])
@never_cache
@transaction.atomic
def setup(request):
    own = owner(request)
    # Serialize submissions across browser tabs and owners of the same shop.
    shop = Shop.objects.select_for_update().get(pk=own.shop_id)
    if shop.onboarding_completed_at:
        return redirect("owner_dashboard")
    if shop.onboarding_catalog_saved_at:
        return redirect("owner_onboarding_branch")
    branches = list(Branch.objects.select_for_update().order_by("pk"))
    config, _ = Settings.objects.get_or_create(shop=shop)
    services = list(Service.objects.filter(archived_at=None).order_by("name"))
    variants = list(PieceVariant.objects.filter(active=True, piece_item__archived_at=None)
                    .select_related("piece_item").order_by("piece_item__name", "label"))
    data = request.POST if request.method == "POST" else None
    service_forms = Services(data, prefix="services", records=services, initial=[
        {"record": s.pk, "name": s.name, "mode": s.mode, "price": s.price} for s in services
    ] or [{"name": "Wash + Dry + Fold", "mode": "kg"}, {"name": "Wash + Dry", "mode": "kg"}])
    piece_forms = Pieces(data, prefix="pieces", records=variants, initial=[
        {"record": v.pk, "name": v.piece_item.name, "label": v.label, "price": v.price} for v in variants
    ] or [{"name": "Plastic", "label": "Each"}])
    limits = LimitsForm(data)
    if request.method == "POST":
        valid = [service_forms.is_valid(), piece_forms.is_valid(), limits.is_valid()]
        if all(valid):
            now = timezone.now()
            for form in service_forms:
                row = form.cleaned_data
                if not row:
                    continue
                obj = service_forms.records.get(row.get("record"))
                if row.get("DELETE"):
                    if obj:
                        obj.archived_at = now
                        obj.save(update_fields=["archived_at"])
                    continue
                obj = obj or Service(shop=shop)
                obj.name, obj.mode, obj.price = row["name"], row["mode"], row["price"]
                obj.save()
            for form in piece_forms:
                row = form.cleaned_data
                if not row:
                    continue
                variant = piece_forms.records.get(row.get("record"))
                if row.get("DELETE"):
                    if variant:
                        variant.active = False
                        variant.save(update_fields=["active"])
                        if not PieceVariant.objects.filter(piece_item=variant.piece_item, active=True).exists():
                            variant.piece_item.archived_at = now
                            variant.piece_item.save(update_fields=["archived_at"])
                    continue
                if variant:
                    item = variant.piece_item
                    item.name = row["name"]
                    item.save(update_fields=["name"])
                else:
                    item, _ = PieceItem.objects.get_or_create(shop=shop, name=row["name"], archived_at=None)
                    variant = PieceVariant(shop=shop, piece_item=item)
                variant.label, variant.price = row["label"], row["price"]
                variant.save()
            config.min_kg = limits.cleaned_data["min_kg"]
            config.kg_per_load = limits.cleaned_data["kg_per_load"]
            config.version += 1
            config.save()
            shop.onboarding_catalog_saved_at = now
            shop.save(update_fields=["onboarding_catalog_saved_at"])
            for branch in branches:
                audit(branch, "settings_updated", "Owner shop catalog saved", owner=own.email)
            return redirect("owner_onboarding_branch")
    return render(request, "owner/onboarding.html", {
        "services": service_forms, "pieces": piece_forms, "limits": limits,
        "onboarding": True,
    }, status=422 if request.method == "POST" else 200)


@require_http_methods(["GET", "POST"])
@never_cache
@transaction.atomic
def branch(request):
    own = owner(request)
    shop = Shop.objects.select_for_update().get(pk=own.shop_id)
    if shop.onboarding_completed_at:
        return redirect("owner_onboarding_device")
    if not shop.onboarding_catalog_saved_at:
        return redirect("owner_onboarding")
    # Reopened test shops keep their first branch rather than adding a duplicate.
    branches = list(Branch.objects.select_for_update().order_by("pk"))
    config = Settings.objects.select_for_update().get(shop=shop)
    existing = min(branches, key=lambda item: item.number, default=None)
    instance = existing or Branch(shop=shop, code="ONE")
    form = BranchForm(request.POST if request.method == "POST" else None, instance=instance)
    form.fields["name"].label = "Branch name"
    form.fields["code"].label = "Branch code"
    form.fields["code"].widget.attrs["spellcheck"] = "false"
    form.fields["opening_time"].help_text = "Use the branch’s local time."
    form.fields["closing_time"].help_text = "Overnight hours work. Matching times mean open 24 hours."
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                if not existing:
                    saved.number = (Branch.objects.aggregate(n=Max("number"))["n"] or 0) + 1
                saved.save()
                config.version += 1
                config.save(update_fields=["version"])
                shop.onboarding_completed_at = timezone.now()
                shop.save(update_fields=["onboarding_completed_at"])
                audit(saved, "branch_updated" if existing else "branch_created",
                      "Owner branch setup completed", owner=own.email)
        except (ValidationError, IntegrityError) as error:
            form.add_error(None, " ".join(error.messages) if isinstance(error, ValidationError)
                           else "A branch with these values already exists. Choose a different code and save again.")
        else:
            return redirect("owner_onboarding_device")
    return render(request, "owner/onboarding_branch.html", {
        "form": form, "onboarding": True, "editing_branch": existing,
    }, status=422 if request.method == "POST" else 200)


@require_http_methods(["GET", "POST"])
@never_cache
def device(request):
    owner(request)
    branch = Branch.objects.order_by("number").first()
    if not branch:
        return redirect("owner_branch_new")
    if request.method == "POST":
        if request.POST.get("setup_device") == "yes":
            return redirect(reverse("owner_home") + f"?branch={branch.pk}&setup=shared#add-device")
        return redirect("owner_dashboard")
    return render(request, "owner/onboarding_device.html", {"onboarding": True, "setup_branch": branch})
