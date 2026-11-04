from django.db import transaction
from django.http import HttpResponseForbidden
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from core.models import ShopOwner
from core.tenancy import shop_context


def approved_owner(sociallogin):
    if sociallogin.account.provider != "google":
        return None
    verified = [e.email.casefold() for e in sociallogin.email_addresses if e.verified]
    owners = list(
        ShopOwner.unscoped.filter(
            email__in=verified, active=True, shop__archived_at=None
        ).select_related("shop")
    )
    # Existing email capitalization is handled by the CLI, plus a case-insensitive fallback.
    if not owners:
        for email in verified:
            owner = (
                ShopOwner.unscoped.filter(
                    email__iexact=email, active=True, shop__archived_at=None
                )
                .select_related("shop")
                .first()
            )
            if owner:
                owners.append(owner)
    if len({o.pk for o in owners}) != 1:
        return None
    return owners[0]


class OwnerAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class OwnerSocialAdapter(DefaultSocialAccountAdapter):
    def _owner(self, sociallogin):
        owner = approved_owner(sociallogin)
        if not owner or (
            sociallogin.is_existing
            and owner.user_id
            and owner.user_id != sociallogin.user.pk
        ):
            raise ImmediateHttpResponse(
                HttpResponseForbidden(
                    "This Google account is not allowed to access Washday. Ask the shop owner to check the allow-list."
                )
            )
        if owner.user_id and not sociallogin.is_existing:
            raise ImmediateHttpResponse(
                HttpResponseForbidden(
                    "This owner is already linked to a different Google account."
                )
            )
        if (
            sociallogin.is_existing
            and ShopOwner.unscoped.filter(user_id=sociallogin.user.pk)
            .exclude(pk=owner.pk)
            .exists()
        ):
            raise ImmediateHttpResponse(
                HttpResponseForbidden(
                    "This Google account is already linked to another owner record."
                )
            )
        return owner

    def pre_social_login(self, request, sociallogin):
        owner = self._owner(sociallogin)
        if sociallogin.is_existing and not owner.user_id:
            with shop_context(owner.shop_id), transaction.atomic():
                row = ShopOwner.objects.select_for_update().get(pk=owner.pk)
                if row.user_id and row.user_id != sociallogin.user.pk:
                    raise ImmediateHttpResponse(
                        HttpResponseForbidden("Owner account link does not match.")
                    )
                row.user = sociallogin.user
                row.save(update_fields=["user"])

    def is_open_for_signup(self, request, sociallogin):
        return bool(self._owner(sociallogin))

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        owner = self._owner(sociallogin)
        with shop_context(owner.shop_id):
            row = ShopOwner.objects.select_for_update().get(pk=owner.pk)
            if row.user_id:
                raise ImmediateHttpResponse(
                    HttpResponseForbidden(
                        "Owner already linked. Sign in with the linked Google account."
                    )
                )
            user = super().save_user(request, sociallogin, form)
            row.user = user
            row.save(update_fields=["user"])
        return user
