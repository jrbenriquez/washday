import csv
import io
import json
from datetime import datetime, time, timedelta, timezone as utc
from unittest.mock import patch, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from backups.drive import DriveClient, DriveError, decrypt, encrypt
from backups.models import DriveBackup, ExportRun
from backups.reports import build_reports
from backups.scheduling import first_run, following_run
from backups.worker import process_backup, run_due
from core.models import Shop, ShopOwner
from core.tenancy import shop_context
from customers.models import Customer
from events.models import Event
from jobs.models import Job, JobLine


@pytest.fixture
def drive_setup(setup_shop, settings, client):
    settings.GOOGLE_DRIVE_CLIENT_ID = "test-client"
    settings.GOOGLE_DRIVE_CLIENT_SECRET = "test-secret"
    settings.GOOGLE_DRIVE_REDIRECT_URI = (
        "http://testserver/owner/drive-exports/callback/"
    )
    settings.GOOGLE_DRIVE_TOKEN_KEY = Fernet.generate_key().decode()
    user = get_user_model().objects.create_user(username="drive-owner")
    owner = ShopOwner.objects.create(
        shop=setup_shop["shop"], email="drive@example.com", user=user
    )
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    config = DriveBackup.objects.create(
        shop=setup_shop["shop"],
        connected_by=owner,
        account_email="drive@example.com",
        refresh_token_encrypted=encrypt("refresh-secret"),
        folder_id="parent-folder",
        folder_name="Reports",
        enabled=True,
        next_run_at=timezone.now() - timedelta(minutes=1),
    )
    return {**setup_shop, "client": client, "config": config, "owner": owner}


def test_credentials_encrypted_and_wrong_key_fails(settings):
    settings.GOOGLE_DRIVE_TOKEN_KEY = Fernet.generate_key().decode()
    token = encrypt("private-token")
    assert "private-token" not in token
    assert decrypt(token) == "private-token"
    settings.GOOGLE_DRIVE_TOKEN_KEY = Fernet.generate_key().decode()
    with pytest.raises(DriveError, match="cannot be decrypted"):
        decrypt(token)


def test_calendar_recurrence_and_dst():
    now = datetime(2026, 11, 4, 13, tzinfo=utc.utc)
    run = first_run(now, time(22), "Asia/Manila")
    assert run == datetime(2026, 11, 4, 14, tzinfo=utc.utc)
    config = Mock(timezone="Asia/Manila", every_days=7, local_time=time(22))
    assert following_run(run, config) == run + timedelta(days=7)
    assert first_run(run, time(22), "Asia/Manila") == run + timedelta(days=1)
    # Across US spring DST, recurring wall time remains 10 PM (23-hour day).
    config = Mock(timezone="America/New_York", every_days=1, local_time=time(22))
    previous = datetime(2026, 3, 8, 3, tzinfo=utc.utc)
    assert following_run(previous, config) == datetime(2026, 3, 9, 2, tzinfo=utc.utc)
    # Nonexistent 02:30 normalizes forward; fall-back 01:30 uses its first occurrence.
    assert first_run(
        datetime(2026, 3, 8, tzinfo=utc.utc), time(2, 30), "America/New_York"
    ) == datetime(2026, 3, 8, 7, 30, tzinfo=utc.utc)


def test_reports_are_tenant_safe_daily_and_have_no_credentials(drive_setup):
    s = drive_setup
    Customer.objects.create(shop=s["shop"], name="=FORMULA", phone="+63912345")
    other = Shop.objects.create(name="Other shop", code="OTHER")
    with shop_context(other):
        Customer.objects.create(shop=other, name="NEVER EXPORT THIS")
    moment = datetime(2026, 11, 4, 14, tzinfo=utc.utc)
    job = Job.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        number=1001,
        kg=1,
        total=42,
        received_at=moment - timedelta(days=1),
        paid_at=moment,
    )
    JobLine.objects.create(
        shop=s["shop"], job=job, label="Wash", amount=42, kind="service"
    )
    Event.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        seq=1,
        type="paid",
        payload={"job_id": str(job.pk)},
        occurred_at=moment,
    )
    # These timestamps fall on Nov 5 in Manila and must not appear in Nov 4's activity CSV.
    Event.objects.create(
        shop=s["shop"],
        branch=s["branch"],
        seq=2,
        type="tomorrow",
        payload={},
        occurred_at=datetime(2026, 11, 4, 16, tzinfo=utc.utc),
    )
    files = {
        name: data for name, data, _ in build_reports(s["shop"], moment, "Asia/Manila")
    }
    snapshot = json.loads(files["snapshot.json"])
    assert "NEVER EXPORT THIS" not in files["snapshot.json"].decode()
    assert "pin_hash" not in files["snapshot.json"].decode()
    assert "refresh-secret" not in files["snapshot.json"].decode()
    assert "key_hash" not in files["snapshot.json"].decode()
    assert len(snapshot["tables"]["events.Event"]) == 2
    events = list(
        csv.DictReader(io.StringIO(files["events_event.csv"].decode("utf-8-sig")))
    )
    assert len(events) == 1 and events[0]["type"] == "paid"
    assert str(job.pk) in files["jobs_job.csv"].decode()
    assert str(job.pk) in files["jobs_jobline.csv"].decode()
    assert "'=FORMULA" in files["customers_customer.csv"].decode()
    assert "'+63912345" in files["customers_customer.csv"].decode()
    assert json.loads(files["manifest.json"])["report_date"] == "2026-11-04"


def test_oauth_pkce_and_state_binding(drive_setup):
    c = drive_setup["client"]
    r = c.post("/owner/drive-exports/connect/")
    q = parse_qs(urlsplit(r.url).query)
    assert q["access_type"] == ["offline"]
    assert q["code_challenge_method"] == ["S256"]
    assert "drive.file" in q["scope"][0]
    with patch("backups.views.tokens") as tokens:
        assert (
            c.get(
                "/owner/drive-exports/callback/", {"state": "wrong", "code": "code"}
            ).status_code
            == 403
        )
        tokens.assert_not_called()


def test_oauth_callback_stores_encrypted_token_and_resets_destination(drive_setup):
    c = drive_setup["client"]
    q = parse_qs(urlsplit(c.post("/owner/drive-exports/connect/").url).query)
    with (
        patch(
            "backups.views.tokens",
            return_value={
                "access_token": "access",
                "refresh_token": "new-refresh",
                "scope": "https://www.googleapis.com/auth/drive.file",
            },
        ),
        patch("backups.views.http", return_value={"email": "new@example.com"}),
    ):
        r = c.get(
            "/owner/drive-exports/callback/", {"state": q["state"][0], "code": "code"}
        )
    assert r.status_code == 302
    config = drive_setup["config"]
    config.refresh_from_db()
    assert decrypt(config.refresh_token_encrypted) == "new-refresh"
    assert config.account_email == "new@example.com"
    assert not config.folder_id and not config.enabled
    # Callback state is single use.
    assert (
        c.get(
            "/owner/drive-exports/callback/", {"state": q["state"][0], "code": "code"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("reason", ["expired", "cancelled", "scope"])
def test_oauth_failures_keep_existing_connection(drive_setup, reason):
    c = drive_setup["client"]
    q = parse_qs(urlsplit(c.post("/owner/drive-exports/connect/").url).query)
    session = c.session
    if reason == "expired":
        pending = session["drive_oauth"]
        pending["at"] -= 601
        session["drive_oauth"] = pending
        session.save()
    with patch(
        "backups.views.tokens",
        return_value={
            "access_token": "access",
            "refresh_token": "new",
            "scope": "email",
        },
    ):
        r = c.get(
            "/owner/drive-exports/callback/",
            {
                "state": q["state"][0],
                "code": "code",
                **({"error": "access_denied"} if reason == "cancelled" else {}),
            },
        )
    assert r.status_code == (403 if reason == "expired" else 302)
    config = drive_setup["config"]
    config.refresh_from_db()
    assert decrypt(config.refresh_token_encrypted) == "refresh-secret"


def test_owner_only_csrf_and_method_protection(drive_setup):
    c = Client()
    for path in ("", "picker-token/", "export-now/", "disconnect/"):
        assert c.post("/owner/drive-exports/" + path).url == "/owner/login/"
    c.force_login(
        drive_setup["owner"].user, backend="django.contrib.auth.backends.ModelBackend"
    )
    assert c.get("/owner/drive-exports/disconnect/").status_code == 405
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(
        drive_setup["owner"].user, backend="django.contrib.auth.backends.ModelBackend"
    )
    assert csrf.post("/owner/drive-exports/export-now/").status_code == 403
    assert c.get("/owner/drive-exports/").status_code == 200


def test_schedule_validation_and_shop_isolation(drive_setup):
    c = drive_setup["client"]
    r = c.post(
        "/owner/drive-exports/",
        {
            "enabled": "on",
            "every_days": "0",
            "local_time": "22:00",
            "timezone": "No/Such_Zone",
        },
    )
    assert r.status_code == 422
    r = c.post(
        "/owner/drive-exports/",
        {
            "enabled": "on",
            "every_days": "7",
            "local_time": "22:00",
            "timezone": "Asia/Manila",
        },
    )
    assert r.status_code == 302
    config = drive_setup["config"]
    config.refresh_from_db()
    assert config.every_days == 7 and config.next_run_at > timezone.now()
    other = Shop.objects.create(name="Other", code="TWO")
    with shop_context(other):
        user = get_user_model().objects.create_user(username="other-owner")
        ShopOwner.objects.create(shop=other, email="other@example.com", user=user)
    c.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    assert c.post("/owner/drive-exports/disconnect/").status_code == 302
    config.refresh_from_db()
    assert config.folder_id == "parent-folder"


def test_folder_selection_validates_with_google(drive_setup):
    c = drive_setup["client"]
    with patch("backups.views.DriveClient") as drive:
        drive.return_value.folder.return_value = {"id": "selected", "name": "Selected"}
        assert (
            c.post(
                "/owner/drive-exports/folder/", {"folder_id": "selected"}
            ).status_code
            == 302
        )
        drive.return_value.folder.assert_called_once_with("selected")
        drive.return_value.create_folder.return_value = {
            "id": "created",
            "name": "New reports",
        }
        assert (
            c.post(
                "/owner/drive-exports/folder/", {"new_name": "New reports"}
            ).status_code
            == 302
        )
        drive.return_value.create_folder.assert_called_once_with("New reports")
        assert (
            c.post(
                "/owner/drive-exports/folder/", {"folder_id": "bad'query"}
            ).status_code
            == 422
        )
    config = drive_setup["config"]
    config.refresh_from_db()
    assert config.folder_id == "created"


def test_folder_must_be_writable_and_picker_token_is_not_cached(drive_setup):
    with (
        patch("backups.drive.tokens", return_value={"access_token": "short-lived"}),
        patch(
            "backups.drive.http",
            return_value={
                "mimeType": "application/vnd.google-apps.folder",
                "capabilities": {"canAddChildren": False},
            },
        ),
    ):
        drive = DriveClient(drive_setup["config"])
        with pytest.raises(DriveError, match="writable"):
            drive.folder("folder")
    with patch("backups.views.DriveClient") as drive:
        drive.return_value.access_token = "short-lived"
        r = drive_setup["client"].post("/owner/drive-exports/picker-token/")
        assert r.json() == {"access_token": "short-lived"}
        assert "no-store" in r.headers["Cache-Control"]


def test_worker_success_advances_once_and_reuses_run(drive_setup):
    config = drive_setup["config"]
    original = config.next_run_at
    with patch("backups.worker.DriveClient") as drive:
        drive.return_value.run_folder.return_value = {"id": "dated-folder"}
        assert process_backup(config.pk)
        run = ExportRun.objects.get(backup=config)
        assert run.status == "success" and run.folder_id == "dated-folder"
        assert drive.return_value.upload.call_count == 26
        assert not process_backup(config.pk)
        assert drive.return_value.run_folder.call_count == 1
    config.refresh_from_db()
    assert config.next_run_at.date() == (original + timedelta(days=1)).date()
    assert config.locked_until is None


def test_worker_failure_retries_same_folder_and_schedule(drive_setup):
    config = drive_setup["config"]
    original = config.next_run_at
    with patch("backups.worker.DriveClient") as drive:
        drive.return_value.run_folder.return_value = {"id": "dated-folder"}
        drive.return_value.upload.side_effect = DriveError(
            "Google Drive request failed."
        )
        assert not process_backup(config.pk)
        run = ExportRun.objects.get(backup=config)
        assert run.status == "failed" and run.attempts == 1
        config.refresh_from_db()
        assert config.next_run_at == original
        assert not process_backup(config.pk)
        ExportRun.objects.filter(pk=run.pk).update(
            retry_at=timezone.now() - timedelta(seconds=1)
        )
        drive.return_value.upload.side_effect = None
        assert process_backup(config.pk)
        run.refresh_from_db()
        assert run.attempts == 2 and run.status == "success"
        assert ExportRun.objects.count() == 1
        assert (
            drive.return_value.run_folder.call_args_list[0]
            == drive.return_value.run_folder.call_args_list[1]
        )


def test_active_lease_blocks_worker_and_settings_changes(drive_setup):
    config = drive_setup["config"]
    DriveBackup.objects.filter(pk=config.pk).update(
        locked_until=timezone.now() + timedelta(minutes=10)
    )
    with patch("backups.worker.DriveClient") as drive:
        assert not process_backup(config.pk)
        drive.assert_not_called()
    assert drive_setup["client"].post("/owner/drive-exports/", {}).status_code == 409
    assert (
        drive_setup["client"]
        .post("/owner/drive-exports/folder/", {"new_name": "Folder"})
        .status_code
        == 422
    )


def test_manual_export_runs_while_paused_and_disconnect_cancels(drive_setup):
    config = drive_setup["config"]
    DriveBackup.objects.filter(pk=config.pk).update(enabled=False, next_run_at=None)
    c = drive_setup["client"]
    c.post("/owner/drive-exports/export-now/")
    c.post("/owner/drive-exports/export-now/")
    assert ExportRun.objects.count() == 1
    with patch("backups.worker.DriveClient") as drive:
        drive.return_value.run_folder.return_value = {"id": "manual-folder"}
        assert run_due() == 1
    config.refresh_from_db()
    assert config.next_run_at is None
    c.post("/owner/drive-exports/export-now/")
    c.post("/owner/drive-exports/disconnect/")
    config.refresh_from_db()
    assert not config.refresh_token_encrypted and not config.folder_id
    assert ExportRun.objects.filter(status="cancelled").count() == 1
    assert run_due() == 0


def test_archived_shop_or_inactive_owner_skipped(drive_setup):
    config = drive_setup["config"]
    ShopOwner.objects.filter(pk=drive_setup["owner"].pk).update(active=False)
    with patch("backups.worker.DriveClient") as drive:
        assert not process_backup(config.pk)
        drive.assert_not_called()


def test_drive_upload_uses_related_multipart_and_updates_existing(drive_setup):
    with patch("backups.drive.tokens", return_value={"access_token": "access"}):
        drive = DriveClient(drive_setup["config"])
    with patch.object(
        drive, "request", side_effect=[{"files": []}, {"id": "file"}]
    ) as request:
        drive.upload("folder", "test.csv", b"name\r\nTEST\r\n", "text/csv")
        method, path = request.call_args.args
        assert method == "POST" and path == "upload/drive/v3/files"
        kwargs = request.call_args.kwargs
        assert kwargs["headers"]["Content-Type"].startswith(
            "multipart/related; boundary="
        )
        assert b"name\r\nTEST\r\n" in kwargs["data"]
    with patch.object(
        drive,
        "request",
        side_effect=[{"files": [{"id": "existing"}]}, {"id": "existing"}],
    ) as request:
        drive.upload("folder", "test.csv", b"new", "text/csv")
        assert request.call_args.args == ("PATCH", "upload/drive/v3/files/existing")


def test_management_command_no_work(db, capsys):
    call_command("run_drive_exports")
    assert "Completed 0" in capsys.readouterr().out


def test_retry_waiting_shop_does_not_consume_tick_limit(drive_setup):
    config = drive_setup["config"]
    ExportRun.objects.create(
        shop=config.shop,
        backup=config,
        scheduled_for=config.next_run_at,
        status="failed",
        retry_at=timezone.now() + timedelta(minutes=5),
    )
    other = Shop.objects.create(name="Healthy", code="HEALTHY")
    with shop_context(other):
        own = ShopOwner.objects.create(shop=other, email="healthy@example.com")
        healthy = DriveBackup.objects.create(
            shop=other,
            connected_by=own,
            refresh_token_encrypted=encrypt("refresh"),
            folder_id="parent",
            enabled=True,
            next_run_at=timezone.now() - timedelta(seconds=1),
        )
    with patch("backups.worker.process_backup", return_value=True) as process:
        assert run_due(limit=1) == 1
        process.assert_called_once_with(healthy.pk)


def test_retry_folder_is_found_by_stable_run_property(drive_setup):
    with patch("backups.drive.tokens", return_value={"access_token": "access"}):
        drive = DriveClient(drive_setup["config"])
    with patch.object(drive, "folder"), patch.object(drive, "create_folder") as create:
        with patch.object(
            drive,
            "request",
            return_value={"files": [{"id": "existing", "name": "Existing"}]},
        ):
            assert drive.run_folder("parent", "Date", "run-id")["id"] == "existing"
            create.assert_not_called()
