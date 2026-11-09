"""Exercise the standard hijack endpoints through Washday's tenancy middleware."""

import pytest
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import Branch, Shop, ShopOwner
from core.tenancy import shop_context


@pytest.fixture
def identities(setup_shop):
    users = get_user_model().objects
    operator = users.create_superuser("operator", "operator@example.invalid", "test-only")
    target = users.create_user("owner", "owner@example.invalid")
    ShopOwner.objects.create(shop=setup_shop["shop"], user=target, email=target.email)
    other_shop = Shop.objects.create(name="Other shop", code="OTHER", onboarding_completed_at=timezone.now())
    with shop_context(other_shop):
        other_branch = Branch.objects.create(shop=other_shop, name="Other branch", number=1, code="OTHER")
        ShopOwner.objects.create(shop=other_shop, user=operator, email=operator.email)
    return operator, target, other_branch


def sign_in(client, user):
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")


def test_admin_acquire_owner_tenancy_banner_and_release(client, identities, setup_shop):
    operator, target, other_branch = identities
    sign_in(client, operator)
    response = client.get(reverse("admin:auth_user_changelist"))
    assert response.status_code == 200
    assert f'data-hijack-user="{target.pk}"'.encode() in response.content
    assert reverse("hijack:acquire").encode() in response.content
    response = client.post(reverse("hijack:acquire"), {"user_pk": target.pk}, follow=True)
    assert response.status_code == 200
    assert int(client.session[SESSION_KEY]) == target.pk
    assert response.wsgi_request.owner.user_id == target.pk
    assert response.context["shop"] == setup_shop["shop"]
    assert list(response.context["branches"]) == [setup_shop["branch"]]
    assert b'id="djhj"' in response.content
    assert reverse("hijack:release").encode() in response.content
    assert b"stop impersonating" in response.content
    assert client.get(reverse("owner_branch_edit", args=[other_branch.pk])).status_code == 404
    assert client.get(reverse("admin:index")).status_code == 302

    response = client.post(reverse("hijack:release"), {"next": reverse("admin:auth_user_changelist")}, follow=True)
    assert response.status_code == 200
    assert int(client.session[SESSION_KEY]) == operator.pk
    assert not client.session.get("hijack_history")
    assert b'id="djhj"' not in response.content
    response = client.get(reverse("owner_home"))
    assert response.context["shop"] == other_branch.shop
    assert list(response.context["branches"]) == [other_branch]


@pytest.mark.parametrize("kind", ["anonymous", "owner", "staff"])
def test_unauthorized_acquire(client, identities, kind):
    operator, target, _ = identities
    if kind != "anonymous":
        user = target if kind == "owner" else get_user_model().objects.create_user("staff", is_staff=True)
        sign_in(client, user)
    response = client.post(reverse("hijack:acquire"), {"user_pk": operator.pk})
    assert response.status_code == (302 if kind == "anonymous" else 403)
    assert not client.session.get("hijack_history")
    if kind != "anonymous":
        assert int(client.session[SESSION_KEY]) == user.pk


def test_csrf_and_inactive_user_protection(identities):
    operator, target, _ = identities
    client = Client(enforce_csrf_checks=True)
    sign_in(client, operator)
    assert client.post(reverse("hijack:acquire"), {"user_pk": target.pk}).status_code == 403
    client.get(reverse("admin:auth_user_changelist"))
    token = client.cookies["csrftoken"].value
    assert client.post(reverse("hijack:acquire"), {"user_pk": target.pk, "csrfmiddlewaretoken": token}).status_code == 302
    assert client.post(reverse("hijack:release")).status_code == 403
    assert int(client.session[SESSION_KEY]) == target.pk
    assert client.post(reverse("hijack:release"), {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code == 302
    target.is_active = False
    target.save(update_fields=["is_active"])
    assert client.post(reverse("hijack:acquire"), {"user_pk": target.pk, "csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code == 403


@pytest.mark.parametrize("restriction", ["inactive_owner", "archived_shop"])
def test_impersonation_preserves_owner_access_restrictions(client, identities, restriction):
    operator, target, _ = identities
    owner = ShopOwner.unscoped.get(user=target)
    if restriction == "inactive_owner":
        owner.active = False
        with shop_context(owner.shop_id):
            owner.save(update_fields=["active"])
    else:
        from django.utils import timezone

        owner.shop.archived_at = timezone.now()
        owner.shop.save(update_fields=["archived_at"])
    sign_in(client, operator)
    assert client.post(reverse("hijack:acquire"), {"user_pk": target.pk}).status_code == 302
    response = client.get(reverse("owner_home"))
    assert response.status_code == 302
    assert response.url == reverse("owner_login")
    # Release remains reachable even when the target cannot enter the owner workspace.
    assert client.post(reverse("hijack:release")).status_code == 302
    assert int(client.session[SESSION_KEY]) == operator.pk


@pytest.mark.parametrize("path", ["/washday-admin/", "/hijack/acquire/", "/hijack/release/"])
def test_operator_routes_unavailable_on_hub(client, settings, path):
    settings.APP_ROLE = "hub"
    assert client.get(path).status_code == 404
    assert client.post(path).status_code == 404
