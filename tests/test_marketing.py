import uuid

import pytest
from django.contrib.auth.models import Permission
from django.core import signing
from django.test import Client, override_settings
from django.urls import reverse

from marketing.forms import TOKEN_SALT, submission_token
from marketing.models import Inquiry

pytestmark = pytest.mark.django_db
PUBLIC = {"HTTP_HOST": "washdayph.com"}
HOSTS = ["washdayph.com", "www.washdayph.com", "app.washdayph.com", "testserver", "localhost", "127.0.0.1"]


@pytest.fixture(autouse=True)
def marketing_hosts(settings):
    settings.ALLOWED_HOSTS = HOSTS


def payload(**changes):
    return {
        "type": "custom", "name": "Demo Prospect", "email": "prospect@example.test",
        "message": "Can you help with two branches?", "submission_token": submission_token(),
        **changes,
    }


def test_video_first_homepage_is_public_without_shop_or_device(client):
    response = client.get("/", **PUBLIC)
    assert response.status_code == 200
    assert b"washday-commercial.mp4" in response.content
    assert b"captions.vtt" in response.content
    assert b"autoplay" not in response.content
    assert "marketing/home.html" in [t.name for t in response.templates]
    assert client.head("/", **PUBLIC).status_code == 200


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
@override_settings(MARKETING_PREVIEW_HOSTS=("localhost", "127.0.0.1"))
def test_local_public_preview(client, host):
    assert client.get("/contact/", HTTP_HOST=host).status_code == 200


@override_settings(MARKETING_PREVIEW_HOSTS=())
def test_normal_local_app_development_is_preserved(client):
    assert client.get("/owner/login/", HTTP_HOST="localhost").status_code == 200
    assert "marketing/home.html" not in [t.name for t in client.get("/", HTTP_HOST="localhost").templates]


@override_settings(MARKETING_VIDEO_URL="https://storage.example.test/intro.mp4")
def test_video_can_move_to_storage_without_a_template_change(client):
    assert b'https://storage.example.test/intro.mp4' in client.get("/", **PUBLIC).content


def test_contact_options_and_query_selection(client):
    response = client.get("/contact/?type=custom", **PUBLIC)
    form = response.context["form"]
    assert form.initial["type"] == "custom"
    assert len(list(form["type"])) == 2
    assert client.get("/contact/?type=invalid", **PUBLIC).context["form"].initial["type"] == "demo"


@pytest.mark.parametrize("path", ["/owner/", "/jobs/", "/device/setup/", "/washday-admin/", "/sync/push/", "/accounts/google/login/"])
def test_app_paths_are_not_exposed_on_public_host(client, path):
    assert client.get(path, **PUBLIC).status_code == 404


def test_app_host_keeps_existing_root_and_authentication(client):
    response = client.get("/", HTTP_HOST="app.washdayph.com")
    assert "marketing/home.html" not in [t.name for t in response.templates]
    assert client.get("/contact/", HTTP_HOST="app.washdayph.com").status_code == 302
    assert client.get("/owner/login/", HTTP_HOST="app.washdayph.com").status_code == 200


def test_www_redirect_preserves_path_and_query(client):
    response = client.get("/contact/?type=demo", HTTP_HOST="www.washdayph.com")
    assert response.status_code == 301
    assert response.url == "https://washdayph.com/contact/?type=demo"


def test_untrusted_host_is_rejected(client):
    assert client.get("/", HTTP_HOST="untrusted.example").status_code == 400


@override_settings(APP_ROLE="hub")
def test_hub_does_not_serve_marketing_or_accept_inquiries(client):
    assert client.get("/", **PUBLIC).status_code == 404
    assert client.post("/contact/", payload(), **PUBLIC).status_code == 404
    assert not Inquiry.objects.exists()


def test_custom_inquiry_is_saved_once_and_success_has_no_personal_details(client, mailoutbox):
    data = payload(branch_count=3, availability="Tuesday")
    for _ in range(2):
        response = client.post("/contact/", data, **PUBLIC)
        assert response.status_code == 302
        assert response.url == "/contact/thanks/"
    record = Inquiry.objects.get()
    assert record.type == "custom"
    assert record.status == "new"
    assert record.name == data["name"]
    assert record.branch_count is None
    assert record.availability == ""
    response = client.get("/contact/thanks/", **PUBLIC)
    assert b"Your inquiry is saved" in response.content
    assert data["email"].encode() not in response.content
    assert "no-store" in response["Cache-Control"]
    assert not mailoutbox


def test_demo_saves_shop_and_scheduling_preferences(client):
    data = payload(type="demo", shop_name="Sample Laundry", branch_count=2, availability="Tuesday afternoon, Asia/Manila", message="")
    assert client.post("/contact/", data, **PUBLIC).status_code == 302
    record = Inquiry.objects.get()
    assert record.type == "demo"
    assert record.branch_count == 2
    assert record.availability == data["availability"]
    assert record.status == "new"
    assert b"isn\xe2\x80\x99t scheduled yet" in client.get("/contact/thanks/", **PUBLIC).content


@pytest.mark.parametrize("changes,error", [
    ({"email": "broken"}, "email"),
    ({"type": "demo", "shop_name": ""}, "shop_name"),
    ({"message": ""}, "message"),
    ({"type": "forged"}, "type"),
    ({"type": "demo", "shop_name": "Shop", "branch_count": 0}, "branch_count"),
    ({"type": "demo", "shop_name": "Shop", "branch_count": 1000}, "branch_count"),
    ({"message": "x"*4001}, "message"),
    ({"submission_token": "forged"}, "submission_token"),
])
def test_invalid_submissions_preserve_input_and_do_not_save(client, changes, error):
    response = client.post("/contact/", payload(**changes), **PUBLIC)
    assert response.status_code == 200
    assert error in response.context["form"].errors
    assert response.context["form"]["name"].value() == "Demo Prospect"
    assert not Inquiry.objects.exists()


def test_expired_token_and_honeypot_are_rejected(client, monkeypatch):
    token = submission_token()
    import time
    now = time.time()
    monkeypatch.setattr(signing.time, "time", lambda: now + 7201)
    assert "submission_token" in client.post("/contact/", payload(submission_token=token), **PUBLIC).context["form"].errors
    assert client.post("/contact/", payload(website="spam.example"), **PUBLIC).context["form"].non_field_errors()
    assert not Inquiry.objects.exists()


def test_csrf_is_required(client):
    strict = Client(enforce_csrf_checks=True)
    assert strict.post("/contact/", payload(), **PUBLIC).status_code == 403


def test_confirmation_requires_prior_submission(client):
    assert client.get("/contact/thanks/", **PUBLIC).url == "/contact/"


def test_public_request_skips_tenant_and_device_authentication(client, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Public visitors must not enter device authentication")
    monkeypatch.setattr("core.middleware.authenticate_device", unexpected)
    assert client.get("/contact/", **PUBLIC).status_code == 200


def test_inquiry_admin_requires_operator_permission(client, django_user_model):
    inquiry = Inquiry.objects.create(submission_id=uuid.uuid4(),type="custom",name="Prospect",email="prospect@example.test",message="Hello")
    user = django_user_model.objects.create_user(username="limited-operator", is_staff=True)
    client.force_login(user)
    url = reverse("admin:marketing_inquiry_change", args=[inquiry.pk])
    assert client.get(url).status_code == 403
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="marketing", codename__in=["view_inquiry","change_inquiry"]))
    assert client.get(url).status_code == 200
    response = client.post(url, {"status":"contacted","internal_notes":"Follow up next week","name":"Changed"})
    assert response.status_code == 302
    inquiry.refresh_from_db()
    assert inquiry.status == "contacted"
    assert inquiry.name == "Prospect"
    assert inquiry.internal_notes == "Follow up next week"
    assert client.post(reverse("admin:marketing_inquiry_add"), {}).status_code == 403
