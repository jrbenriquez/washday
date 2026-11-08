import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from core.models import ShopOwner
from core.tenancy import current_shop

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return get_user_model().objects.create_superuser(
        username="admin-test", email="admin@example.com", password="test-admin-password"
    )


def test_admin_login_is_public_without_device_and_default_path_is_not_routed(client):
    assert reverse("admin:index") == "/washday-admin/"
    response = client.get("/washday-admin/")
    assert response.status_code == 302
    assert response.url == "/washday-admin/login/?next=/washday-admin/"
    assert client.get("/washday-admin/login/").status_code == 200
    assert client.get("/washday-admin").url == "/washday-admin/"
    # No default Django admin route was added.
    from django.urls import Resolver404, resolve

    with pytest.raises(Resolver404):
        resolve("/admin/")


def test_admin_password_login_and_user_management(client, admin_user):
    response = client.post(
        reverse("admin:login"),
        {
            "username": admin_user.username,
            "password": "test-admin-password",
            "next": reverse("admin:index"),
        },
    )
    assert response.status_code == 302 and response.url == reverse("admin:index")
    assert client.get(reverse("admin:index")).status_code == 200
    assert client.get(reverse("admin:auth_user_changelist")).status_code == 200
    assert client.get(reverse("admin:auth_group_changelist")).status_code == 200


@pytest.mark.parametrize("is_active,is_staff", [(True, False), (False, True)])
def test_admin_rejects_nonstaff_and_inactive_accounts(client, is_active, is_staff):
    user = get_user_model().objects.create_user(
        username="not-admin",
        password="test-password",
        is_active=is_active,
        is_staff=is_staff,
    )
    response = client.post(
        reverse("admin:login"),
        {
            "username": user.username,
            "password": "test-password",
        },
    )
    assert response.status_code == 200 and response.context["form"].errors
    assert "_auth_user_id" not in client.session


def test_google_owner_does_not_gain_admin_access(client, setup_shop):
    user = get_user_model().objects.create_user(username="owner-test")
    ShopOwner.objects.create(
        shop=setup_shop["shop"], user=user, email="owner@example.com"
    )
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get("/owner/dashboard/").status_code == 200
    response = client.get(reverse("admin:index"))
    assert response.status_code == 302 and response.url.startswith(
        reverse("admin:login")
    )


def test_staff_permissions_control_admin_models(client):
    user = get_user_model().objects.create_user(username="limited-admin", is_staff=True)
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get(reverse("admin:index")).status_code == 200
    assert client.get(reverse("admin:auth_user_changelist")).status_code == 403
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="auth", codename="view_user")
    )
    assert client.get(reverse("admin:auth_user_changelist")).status_code == 200
    assert client.get(reverse("admin:auth_user_add")).status_code == 403


def test_admin_ignores_device_and_development_shop_scope(
    client, admin_user, setup_shop, settings
):
    settings.ENABLE_DEV_BRANCH_SCOPE = True
    settings.DEV_BRANCH_ID = str(setup_shop["branch"].pk)
    client.cookies[settings.DEVICE_COOKIE_NAME] = "invalid-device-token"
    client.force_login(admin_user, backend="django.contrib.auth.backends.ModelBackend")
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200
    assert response.context["shop"] is None and response.context["branch"] is None
    assert not response.wsgi_request.dev_scope
    assert current_shop() == setup_shop["shop"].pk
    assert settings.DEVICE_COOKIE_NAME not in response.cookies


@pytest.mark.parametrize(
    "path",
    [
        "/washday-admin",
        "/washday-admin/",
        "/washday-admin/login/",
        "/washday-admin/auth/user/",
    ],
)
def test_admin_is_unavailable_on_hub(client, admin_user, settings, path):
    settings.APP_ROLE = "hub"
    client.force_login(admin_user, backend="django.contrib.auth.backends.ModelBackend")
    assert client.get(path, follow=True).status_code == 404


def test_admin_login_requires_csrf(admin_user):
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        reverse("admin:login"),
        {
            "username": admin_user.username,
            "password": "test-admin-password",
        },
    )
    assert response.status_code == 403
