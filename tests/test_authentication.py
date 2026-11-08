from datetime import timedelta, time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import pytest
from django.conf import settings as config
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone
from core.models import Shop, ShopOwner, Branch, MachineCategory, Machine
from core.tenancy import shop_context
from people.models import Staff, Device, DeviceSetupCode, Shift
from people.services import (
    save_staff,
    issue_code,
    enroll,
)
from jobs.models import Job
from events.models import Event


@pytest.fixture
def auth(setup_shop, settings):
    settings.DEBUG = True
    settings.ENABLE_DEV_BRANCH_SCOPE = False
    settings.DEVICE_SETUP_ALLOW_BROWSER = True
    s = setup_shop
    b = s["branch"]
    b.closing_time = time(23, 59)
    b.opening_time = time(8)
    b.save(update_fields=["opening_time", "closing_time"])
    staff, _ = save_staff(b, "TEST authenticated staff", "1234")
    user = get_user_model().objects.create_user(
        username="test-google-owner", email="owner@example.com"
    )
    user.set_unusable_password()
    user.save()
    own = ShopOwner.objects.create(shop=s["shop"], email="owner@example.com", user=user)
    shared = Device.objects.create(
        shop=s["shop"], branch=b, name="TEST counter tablet", kind="shared"
    )
    personal = Device.objects.create(
        shop=s["shop"], branch=b, name="TEST personal phone", kind="personal"
    )
    return {
        **s,
        "auth_staff": staff,
        "owner": own,
        "user": user,
        "shared": shared,
        "personal": personal,
    }


def owner_client(a):
    c = Client()
    c.force_login(a["user"], backend="django.contrib.auth.backends.ModelBackend")
    return c


def test_header_branding_requires_authenticated_shop_context(auth):
    from django.utils.html import escape

    c = Client()
    for path in ("/", "/owner/login/", "/device/setup/", f'/device/start/?invite={auth["shared"].pk}'):
        response = c.get(path)
        header = response.content.decode().split('<header class="top">')[1].split("</header>")[0]
        assert "WashDay" in header
        assert auth["shop"].name not in header
        assert "img/app-icon.svg" in header
    assert escape(auth["shop"].name).encode() in owner_client(auth).get("/owner/").content
    staff, _ = staff_client(auth)
    assert escape(auth["shop"].name).encode() in staff.get("/jobs/").content


def test_owner_can_upload_replace_and_clear_shop_logo(auth, settings, tmp_path):
    from io import BytesIO
    from PIL import Image
    from django.core.files.uploadedfile import SimpleUploadedFile
    from jobs.services import create_job

    settings.MEDIA_ROOT = tmp_path
    c = owner_client(auth)

    def logo():
        image = BytesIO()
        Image.new("RGB", (40, 40), "blue").save(image, format="PNG")
        return SimpleUploadedFile("logo.png", image.getvalue(), content_type="image/png")

    assert c.get("/owner/settings/").status_code == 200
    assert c.post("/owner/settings/", {"name": "My Laundry", "logo": logo()}).status_code == 302
    shop = auth["shop"]
    shop.refresh_from_db()
    first_url = shop.logo.url
    assert shop.logo.name.startswith(f"shops/{shop.pk}/logos/")
    assert shop.logo.storage.exists(shop.logo.name)
    assert first_url.encode() in c.get("/owner/").content
    staff, _ = staff_client(auth)
    assert first_url.encode() in staff.get("/jobs/").content
    job, _ = create_job(job_data(auth), auth["branch"], auth["staff"])
    assert first_url.encode() in staff.get(f"/jobs/{job.number}/").content
    assert b"multipart/form-data" in c.get("/owner/settings/").content
    assert c.post("/owner/settings/", {"name": "My Laundry", "logo": logo()}).status_code == 302
    shop.refresh_from_db()
    assert shop.logo.url != first_url
    invalid = SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")
    assert c.post("/owner/settings/", {"name": "My Laundry", "logo": invalid}).status_code == 422
    shop.refresh_from_db()
    assert shop.logo
    assert c.post("/owner/settings/", {"name": "My Laundry", "logo-clear": "on"}).status_code == 302
    shop.refresh_from_db()
    assert not shop.logo
    assert b"img/app-icon.svg" in c.get("/owner/").content
    assert Client().post("/owner/settings/", {"name": "Intruder"}).url == "/owner/login/"
    assert staff.post("/owner/settings/", {"name": "Intruder"}).url == "/owner/login/"
    shop.refresh_from_db()
    assert shop.name == "My Laundry"


def test_existing_static_shop_logos_remain_usable(auth):
    shop = auth["shop"]
    shop.logo = "img/bula-banlaw.svg"
    shop.save(update_fields=["logo"])
    assert shop.logo_url == "/static/img/bula-banlaw.svg"
    assert b'/static/img/bula-banlaw.svg' in owner_client(auth).get("/owner/").content


def staff_client(a, kind="shared"):
    d = a[kind]
    code, _ = issue_code(d)
    d, token, error = enroll(d, code)
    assert not error
    c = Client()
    c.cookies[config.DEVICE_COOKIE_NAME] = token
    return c, token


def job_data(a, **extra):
    return {"kg": "2", "service": str(a["service"].id), **extra}


def test_no_credentials_and_invalid_keys_cannot_use_staff_or_owner(auth, settings):
    c = Client()
    for url in [
        "/jobs/",
        "/jobs/new/",
        "/customers/search/",
        "/machines/",
        "/supplies/",
        "/shift/",
    ]:
        r = c.get(url)
        assert r.status_code == 302 and r.url == "/device/setup/"
    assert c.get("/owner/").url == "/owner/login/"
    c.cookies[config.DEVICE_COOKIE_NAME] = "invented-credential"
    settings.ENABLE_DEV_BRANCH_SCOPE = True
    settings.DEV_BRANCH_ID = str(auth["branch"].id)
    assert c.get("/jobs/").url == "/device/setup/"
    assert not Job.objects.exists()
    settings.ENABLE_DEV_BRANCH_SCOPE = False
    assert owner_client(auth).get("/jobs/").url == "/device/setup/"


def test_owner_bootstrap_and_owner_scope(auth):
    c = owner_client(auth)
    assert c.get("/owner/").status_code == 200
    assert (
        c.post(
            "/accounts/login/",
            {"login": "owner@example.com", "password": "not-a-password"},
        ).url
        == "/owner/login/"
    )
    assert c.get("/accounts/password/set/").status_code == 403
    other = Shop.objects.create(code="FOREIGN", name="SECRET SHOP")
    with shop_context(other):
        b = Branch.objects.create(shop=other, code="F", name="SECRET BRANCH", number=2)
        d = Device.objects.create(
            shop=other, branch=b, kind="shared", name="SECRET DEVICE"
        )
        staff = Staff.objects.create(
            shop=other, branch=b, name="SECRET STAFF", pin_hash="!"
        )
    assert b"SECRET" not in c.get("/owner/").content
    assert c.post(f"/owner/devices/{d.pk}/revoke/").status_code == 404
    assert c.post(f"/owner/staff/{staff.pk}/", {"active": "0"}).status_code == 404
    assert (
        c.post(
            "/owner/staff/new/", {"branch": str(b.pk), "name": "bad", "pin": "1234"}
        ).status_code
        == 404
    )
    auth["owner"].active = False
    auth["owner"].save(update_fields=["active"])
    assert c.get("/owner/").url == "/owner/login/"


@pytest.fixture
def google(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APP": {
                "client_id": "test-client-id",
                "secret": "test-client-secret",
                "key": "",
            },
            "SCOPE": ["openid", "email", "profile"],
            "OAUTH_PKCE_ENABLED": True,
        }
    }
    settings.GOOGLE_OAUTH_CONFIGURED = True


def google_login(c, email, verified=True, state_override=None):
    response = c.post("/accounts/google/login/")
    assert (
        response.status_code == 302
        and urlsplit(response.url).hostname == "accounts.google.com"
    )
    q = parse_qs(urlsplit(response.url).query)
    assert q.get("code_challenge")
    assert q["redirect_uri"] == ["http://testserver/accounts/google/login/callback/"]
    state = state_override or q["state"][0]
    with (
        patch(
            "allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
            return_value={
                "access_token": "test-google-access-token",
                "token_type": "Bearer",
            },
        ),
        patch(
            "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter._fetch_user_info",
            return_value={
                "sub": "test-google-subject",
                "email": email,
                "email_verified": verified,
                "given_name": "TEST",
                "family_name": "Owner",
            },
        ),
    ):
        return c.get(
            "/accounts/google/login/callback/",
            {"code": "test-authorization-code", "state": state},
        )


def test_real_allauth_callback_pipeline_binds_allowlisted_verified_google(auth, google):
    # A fresh allow-listed identity; only Google's network responses are stubbed.
    new = ShopOwner.objects.create(shop=auth["shop"], email="new@example.com")
    c = Client()
    r = google_login(c, "new@example.com")
    assert r.status_code == 302 and r.url == "/owner/"
    new.refresh_from_db()
    assert new.user_id and not new.user.has_usable_password()
    assert c.get("/owner/").status_code == 200
    assert c.session.get_expiry_age() == 14 * 24 * 60 * 60
    from allauth.socialaccount.models import SocialToken

    assert not SocialToken.objects.exists()


@pytest.mark.parametrize(
    "email,verified", [("unknown@example.com", True), ("new@example.com", False)]
)
def test_oauth_unknown_or_unverified_email_denied(auth, google, email, verified):
    ShopOwner.objects.create(shop=auth["shop"], email="new@example.com")
    before = get_user_model().objects.count()
    c = Client()
    r = google_login(c, email, verified)
    assert (
        r.status_code == 403
        and get_user_model().objects.count() == before
        and "_auth_user_id" not in c.session
    )


def test_oauth_state_tamper_does_not_log_in(auth, google):
    c = Client()
    r = google_login(c, "owner@example.com", state_override="not-the-session-state")
    assert "_auth_user_id" not in c.session and r.status_code == 401


def test_owner_forms_issue_hash_only_and_revoke_immediately(auth):
    a = auth
    c = owner_client(a)
    r = c.post(
        "/owner/staff/new/",
        {"branch": str(a["branch"].pk), "name": "TEST new staff", "pin": "4567"},
    )
    assert r.status_code == 200 and b"4567" in r.content
    s = Staff.objects.get(name="TEST new staff")
    assert s.pin_hash != "4567" and check_password("4567", s.pin_hash)
    assert b"4567" not in c.get("/owner/").content
    r = c.post(
        "/owner/devices/new/",
        {"branch": str(a["branch"].pk), "name": "TEST new tablet", "kind": "shared"},
    )
    assert r.status_code == 200 and b"install-qr" in r.content
    d = Device.objects.get(name="TEST new tablet")
    code = r.context["setup_code"]
    assert DeviceSetupCode.objects.get(device=d).code_hash != code
    assert "no-store" in r.headers["Cache-Control"]
    sc = Client()
    r = sc.post("/device/setup/", {"invite": str(d.id), "code": code})
    assert r.status_code == 302
    token = sc.cookies[config.DEVICE_COOKIE_NAME].value
    assert token != d.key_hash
    assert sc.get("/jobs/").status_code == 200
    assert c.post(f"/owner/devices/{d.id}/revoke/").status_code == 302
    assert sc.get("/jobs/").url == "/device/setup/"


def test_install_page_and_manifest_never_enrol(auth):
    d = auth["shared"]
    c = Client()
    code, _ = issue_code(d)
    r = c.get("/device/start/", {"invite": str(d.id)})
    assert r.status_code == 200 and config.DEVICE_COOKIE_NAME not in r.cookies
    assert code.encode() not in r.content
    manifest = c.get("/device/manifest.webmanifest", {"invite": str(d.id)}).json()
    assert manifest["display"] == "standalone" and str(d.id) in manifest["start_url"]
    d.refresh_from_db()
    assert d.key_hash is None


def test_setup_single_use_cookie_flags_and_code_replacement(auth):
    d = auth["shared"]
    code, _ = issue_code(d)
    c = Client()
    r = c.post("/device/setup/", {"invite": str(d.id), "code": code})
    cookie = r.cookies[config.DEVICE_COOKIE_NAME]
    assert (
        cookie["httponly"]
        and cookie["samesite"] == "Lax"
        and int(cookie["max-age"]) == 365 * 24 * 60 * 60
    )
    assert not cookie["secure"]  # local HTTP only; production cookie is Secure
    assert (
        Client().post("/device/setup/", {"invite": str(d.id), "code": code}).status_code
        == 422
    )
    old_token = cookie.value
    old_code, _ = issue_code(d)
    new_code, _ = issue_code(d)
    assert (
        Client()
        .post("/device/setup/", {"invite": str(d.id), "code": old_code})
        .status_code
        == 422
    )
    c2 = Client()
    assert (
        c2.post("/device/setup/", {"invite": str(d.id), "code": new_code}).status_code
        == 302
    )
    c.cookies[config.DEVICE_COOKIE_NAME] = old_token
    assert c.get("/jobs/").url == "/device/setup/"


def test_setup_expiry_wrong_invitation_and_shared_server_lock(auth):
    a = auth
    code, challenge = issue_code(a["shared"])
    personal_code, _ = issue_code(a["personal"])
    assert enroll(a["personal"], code)[2]
    DeviceSetupCode.objects.filter(pk=challenge.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert enroll(a["shared"], code)[2]
    code, _ = issue_code(a["shared"])
    for _ in range(5):
        assert (
            Client()
            .post("/device/setup/", {"invite": str(a["shared"].id), "code": "wrong"})
            .status_code
            == 422
        )
    assert "one minute" in enroll(a["shared"], code)[2]
    Device.objects.filter(pk=a["shared"].id).update(
        setup_locked_until=timezone.now() - timedelta(seconds=1)
    )
    assert not enroll(a["shared"], code)[2]


def test_personal_shift_landing_attribution_end_and_cookie_retention(auth):
    a = auth
    c, token = staff_client(a, "personal")
    assert c.get("/jobs/new/").url == "/shift/"
    r = c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"})
    assert r.status_code == 302 and r.url == "/jobs/"
    assert Shift.objects.filter(device=a["personal"], ended_at=None).count() == 1
    assert c.post("/jobs/new/", job_data(a, pay_method="cash")).status_code == 302
    j = Job.objects.get()
    assert j.created_by == a["auth_staff"] and j.created_device == a["personal"]
    assert Event.objects.get(type="job_created").device == a["personal"]
    assert c.post("/shift/end/").url == "/shift/"
    assert (
        c.cookies[config.DEVICE_COOKIE_NAME].value == token
        and c.get("/jobs/").url == "/shift/"
    )


def test_expiry_and_pin_reset_invalidate_personal_session(auth):
    a = auth
    c, _ = staff_client(a, "personal")
    c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"})
    shift = Shift.objects.get(device=a["personal"], ended_at=None)
    with patch(
        "people.services.timezone.now",
        return_value=shift.ends_at,
    ):
        assert c.get("/jobs/").url == "/shift/"
    shift.refresh_from_db()
    assert shift.ended_by == "expired" and shift.ended_at == shift.ends_at
    c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"})
    save_staff(a["branch"], a["auth_staff"].name, "5678", staff=a["auth_staff"])
    assert c.get("/jobs/").url == "/shift/"
    assert (
        c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"}).status_code
        == 422
    )
    assert (
        c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "5678"}).url
        == "/jobs/"
    )


def test_staff_session_lasts_24_hours_without_branch_hours(auth):
    a = auth
    c, token = staff_client(a, "personal")
    a["branch"].closing_time = None
    a["branch"].save(update_fields=["closing_time"])
    page = c.get("/shift/")
    assert b">Sign in</button>" in page.content
    assert b"disabled" not in page.content
    assert c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"}).url == "/jobs/"
    session = Shift.objects.get(device=a["personal"], ended_at=None)
    assert session.ends_at == session.started_at + timedelta(hours=24)
    # Ordinary activity must not extend the original expiry.
    with patch("people.services.timezone.now", return_value=session.ends_at - timedelta(seconds=1)):
        response = c.get("/jobs/")
        assert response.status_code == 200
        assert b">Sign out</button>" in response.content
        assert timezone.localtime(session.ends_at).isoformat().encode() in response.content
    session.refresh_from_db()
    assert session.ends_at == session.started_at + timedelta(hours=24)
    # An expired session cannot make a write, even while the device stays enrolled.
    with patch("people.services.timezone.now", return_value=session.ends_at):
        assert c.post("/jobs/new/", job_data(a)).url == "/shift/"
    assert not Job.objects.exists()
    assert c.cookies[config.DEVICE_COOKIE_NAME].value == token
    assert c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"}).url == "/jobs/"


def test_branch_closing_does_not_end_staff_session(auth):
    a = auth
    c, _ = staff_client(a, "personal")
    now = timezone.now()
    a["branch"].closing_time = timezone.localtime(now + timedelta(minutes=1)).time().replace(tzinfo=None)
    a["branch"].save(update_fields=["closing_time"])
    with patch("people.services.timezone.now", return_value=now):
        assert c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"}).url == "/jobs/"
    with patch("people.services.timezone.now", return_value=now + timedelta(minutes=2)):
        assert c.get("/jobs/").status_code == 200


def test_inactive_staff_refuse_signin(auth):
    a = auth
    c, _ = staff_client(a, "personal")
    a["auth_staff"].active = False
    a["auth_staff"].save(update_fields=["active"])
    assert c.post("/shift/", {"staff": str(a["auth_staff"].pk), "pin": "1234"}).status_code == 422
    assert not Shift.objects.exists()


def test_shared_unpaid_create_records_device_and_no_shift(auth):
    a = auth
    c, _ = staff_client(a)
    assert c.post("/jobs/new/", job_data(a)).status_code == 302
    j = Job.objects.get()
    assert (
        j.created_by is None
        and j.created_device == a["shared"]
        and not Shift.objects.exists()
    )
    assert a["shared"].name.encode() in c.get(f"/jobs/{j.number}/").content
    assert Event.objects.get(type="job_created").device == a["shared"]


def test_shared_paid_create_requires_pin_per_action_and_preserves_payload(auth):
    a = auth
    c, _ = staff_client(a)
    payload = job_data(
        a, pay_method="gcash", pay_ref="AUTH-REF", addons=[str(a["addon"].pk)]
    )
    r = c.post("/jobs/new/", payload)
    assert (
        r.status_code == 200
        and b"Confirm with your PIN" in r.content
        and not Job.objects.exists()
    )
    assert (
        c.post("/jobs/new/", {**payload, "pin": "9999"}).status_code == 422
        and not Job.objects.exists()
    )
    assert c.post("/jobs/new/", {**payload, "pin": "1234"}).status_code == 302
    j = Job.objects.get()
    assert (
        j.pay_ref == "AUTH-REF"
        and j.created_by == a["auth_staff"]
        and j.lines.filter(kind="addon").count() == 1
    )
    assert c.post("/jobs/new/", payload).status_code == 200 and Job.objects.count() == 1
    assert not any(
        k in e.payload
        for e in Event.objects.all()
        for k in ("pin", "code", "key_hash", "token")
    )


def test_shared_claim_and_manual_override_need_pin_without_partial_writes(auth):
    a = auth
    c, _ = staff_client(a)
    c.post("/jobs/new/", job_data(a))
    j = Job.objects.get()
    first = j.status_id
    ready = __import__("core.models", fromlist=["JobStage"]).JobStage.objects.get(
        is_last=True
    )
    override = {
        "expected": str(first),
        "target": str(ready.pk),
        "reason": "PIN-authorized correction",
    }
    assert (
        b"Confirm with your PIN" in c.post(f"/jobs/{j.number}/stage/", override).content
    )
    j.refresh_from_db()
    assert j.status_id == first
    assert (
        c.post(f"/jobs/{j.number}/stage/", {**override, "pin": "1234"}).status_code
        == 302
    )
    claim = {"expected": str(ready.pk), "pay_method": "cash"}
    assert b"Confirm with your PIN" in c.post(f"/jobs/{j.number}/claim/", claim).content
    assert not Event.objects.filter(type="payment_recorded").exists()
    c.post(f"/jobs/{j.number}/claim/", {**claim, "pin": "1234"})
    j.refresh_from_db()
    assert j.claimed_at and j.paid_at
    assert Event.objects.get(type="job_claimed").actor_staff == a["auth_staff"]


def test_self_service_and_paper_payment_pin_rules(auth):
    a = auth
    b = a["branch"]
    b.simple_mode = False
    b.save(update_fields=["simple_mode"])
    c, _ = staff_client(a)
    category = MachineCategory.objects.create(
        shop=a["shop"], name="Washer", label_prefix="W"
    )
    machine = Machine.objects.create(
        shop=a["shop"], branch=b, category=category, label="W1"
    )
    data = {"service": str(a["load"].pk), "pay_method": "cash"}
    assert (
        b"Confirm with your PIN"
        in c.post(f"/machines/{machine.pk}/start/", data).content
    )
    from machines.models import Load

    assert not Load.objects.exists()
    assert (
        c.post(f"/machines/{machine.pk}/start/", {**data, "pin": "1234"}).status_code
        == 302
    )
    assert Event.objects.get(type="self_service_started").actor_staff == a["auth_staff"]
    day = (timezone.localdate() - timedelta(days=1)).isoformat()
    paper = job_data(
        a,
        paper="1",
        paper_ref="P-44",
        paper_date=day,
        received_time="08:00",
        written_total="100",
        pay_method="cash",
        paid_time="08:10",
    )
    assert b"Confirm with your PIN" in c.post("/jobs/new/?paper=1", paper).content
    assert c.post("/jobs/new/?paper=1", {**paper, "pin": "1234"}).status_code == 302
    assert Job.objects.get().paper_ref == "P-44"


def test_pin_lockout_and_owner_policy_updates(auth):
    a = auth
    c, _ = staff_client(a)
    payload = job_data(a, pay_method="cash", pin="9999")
    for _ in range(5):
        assert c.post("/jobs/new/", payload).status_code == 422
    assert (
        c.post("/jobs/new/", {**payload, "pin": "1234"}).status_code == 422
        and not Job.objects.exists()
    )
    Device.objects.filter(pk=a["shared"].pk).update(
        pin_locked_until=timezone.now() - timedelta(seconds=1)
    )
    assert c.post("/jobs/new/", {**payload, "pin": "1234"}).status_code == 302
    own = owner_client(a)
    assert (
        own.post(
            "/owner/pin-rules/", {"pin_actions": ["create"], "pin_enabled": "on"}
        ).status_code
        == 302
    )
    assert b"Confirm with your PIN" in c.post("/jobs/new/", job_data(a)).content
    own.post("/owner/pin-rules/", {})
    assert c.post("/jobs/new/", job_data(a, pay_method="cash")).status_code == 302


def test_pin_uniqueness_and_no_reactivation_collision(auth):
    a = auth
    with pytest.raises(ValidationError):
        save_staff(a["branch"], "Another", "1234")
    save_staff(a["branch"], a["auth_staff"].name, staff=a["auth_staff"], active=False)
    save_staff(a["branch"], "Replacement", "1234")
    with pytest.raises(ValidationError):
        save_staff(
            a["branch"], a["auth_staff"].name, staff=a["auth_staff"], active=True
        )
    with pytest.raises(ValidationError):
        save_staff(
            a["branch"],
            a["auth_staff"].name,
            "1234",
            staff=a["auth_staff"],
            active=True,
        )


def test_owner_and_staff_posts_require_csrf(auth):
    a = auth
    c = Client(enforce_csrf_checks=True)
    c.force_login(a["user"], backend="django.contrib.auth.backends.ModelBackend")
    assert (
        c.post(
            "/owner/staff/new/",
            {"name": "No CSRF", "branch": str(a["branch"].pk), "pin": "9999"},
        ).status_code
        == 403
    )
    sc, token = staff_client(a)
    c = Client(enforce_csrf_checks=True)
    c.cookies[config.DEVICE_COOKIE_NAME] = token
    assert c.post("/jobs/new/", job_data(a)).status_code == 403


def test_owner_logout_does_not_clear_device_or_staff_identity(auth):
    a = auth
    c, token = staff_client(a)
    c.force_login(a["user"], backend="django.contrib.auth.backends.ModelBackend")
    assert c.get("/owner/").status_code == 200
    assert c.post("/accounts/logout/").status_code == 302
    assert c.cookies[config.DEVICE_COOKIE_NAME].value == token
    assert (
        c.get("/owner/").url == "/owner/login/" and c.get("/jobs/").status_code == 200
    )


def test_production_enrolment_cookie_is_secure_and_browser_shortcut_off(auth, settings):
    a = auth
    settings.DEBUG = False
    settings.DEVICE_SETUP_ALLOW_BROWSER = False
    code, _ = issue_code(a["shared"])
    c = Client()
    r = c.post(
        "/device/setup/", {"invite": str(a["shared"].id), "code": code}, secure=True
    )
    assert r.status_code == 302 and r.cookies[config.DEVICE_COOKIE_NAME]["secure"]
    assert (
        Client()
        .get("/device/setup/", {"invite": str(a["shared"].id)}, secure=True)
        .context["allow_browser"]
        is False
    )


def test_stock_count_without_pin_records_real_device(auth):
    from catalog.models import SupplyType
    from supplies.models import StockCount

    a = auth
    c, _ = staff_client(a)
    supply = SupplyType.objects.create(
        shop=a["shop"], name="TEST actor stock", unit="piece"
    )
    assert (
        c.post("/supplies/count/", {"count_" + str(supply.id): "5"}).status_code == 302
    )
    count = StockCount.objects.get()
    assert count.by is None and count.device == a["shared"]
    assert a["shared"].name.encode() in c.get("/supplies/").content


def test_wrong_branch_personal_staff_id_does_not_open_shift(auth):
    a = auth
    other = Branch.objects.create(
        shop=a["shop"], name="OTHER", code="OTHER", number=2, closing_time=time(23, 59)
    )
    foreign, _ = save_staff(other, "OTHER staff", "1234")
    c, _ = staff_client(a, "personal")
    assert (
        c.post("/shift/", {"staff": str(foreign.id), "pin": "1234"}).status_code == 422
        and not Shift.objects.exists()
    )


def test_unknown_device_kind_fails_closed(auth):
    a = auth
    c, _ = staff_client(a)
    Device.objects.filter(pk=a["shared"].pk).update(kind="invalid")
    assert c.get("/jobs/").url == "/device/setup/"


def test_owner_audit_events_show_owner_actor_in_staff_history(auth):
    a = auth
    own = owner_client(a)
    own.post(
        "/owner/branches/" + str(a["branch"].id) + "/hours/",
        {"opening_time": "08:00", "closing_time": "23:59"},
    )
    staff, _ = staff_client(a)
    response = staff.get("/jobs/?view=history")
    assert (
        b"owner@example.com" in response.content
        and b"Branch opening/closing hours updated" in response.content
    )


def test_manifest_launch_reuses_enrolment_without_redeeming_code_again(auth):
    a = auth
    shared, token = staff_client(a)
    url = "/device/setup/?invite=" + str(a["shared"].id)
    response = shared.get(url, follow=True)
    assert response.status_code == 200 and response.request["PATH_INFO"] == "/jobs/new/"
    assert shared.cookies[config.DEVICE_COOKIE_NAME].value == token
    personal, _ = staff_client(a, "personal")
    personal.post("/shift/", {"staff": str(a["auth_staff"].id), "pin": "1234"})
    url = "/device/setup/?invite=" + str(a["personal"].id)
    response = personal.get(url, follow=True)
    assert response.status_code == 200 and response.request["PATH_INFO"] == "/jobs/"
    personal.post("/shift/end/")
    response = personal.get(url, follow=True)
    assert response.request["PATH_INFO"] == "/shift/"
