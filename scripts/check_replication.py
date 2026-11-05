"""Two real HTTP processes/two SQLite files; no production data or credentials.

This tests protocol recovery, not a physical router outage or hardware rollout.
"""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".agents/work/undo-offline/evidence"
OUT.mkdir(parents=True, exist_ok=True)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait(base):
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health/", timeout=1).close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Private fixture server did not start.")


with tempfile.TemporaryDirectory(prefix="washday-replication-") as temp:
    os.environ.update(
        DJANGO_SETTINGS_MODULE="config.settings",
        APP_ROLE="cloud",
        SQLITE_PATH=str(Path(temp) / "cloud.sqlite3"),
        DJANGO_DEBUG="1",
        ENABLE_DEV_BRANCH_SCOPE="0",
    )
    os.environ.pop("PGDATABASE", None)
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone

    from core.models import Branch, Settings, Shop, ShopOwner
    from core.tenancy import shop_context
    from events.models import Event, HubCredential
    from events.sync.modes import activate_direct, activate_hub, prepare
    from jobs.models import Job
    from owner.workspace import collections
    from people.models import Device
    from people.services import enroll, issue_code

    log = io.StringIO()
    call_command("migrate", stdout=log, verbosity=0)
    call_command("seed_demo", stdout=log)
    shop = Shop.objects.get(code="DEV-ONLY")
    with shop_context(shop):
        branch = Branch.objects.get(code="DEMO")
        branch.simple_mode = False
        branch.save(update_fields=["simple_mode"])
        config = Settings.objects.get()
        config.pin_enabled = False
        config.save()
        device = Device.objects.create(
            shop=shop, branch=branch, name="TEST offline counter", kind="shared"
        )
        code, _ = issue_code(device)
        _, direct_key, error = enroll(device, code)
        assert not error
        key = prepare(branch)
        baseline = Branch.objects.get(pk=branch.pk).event_seq
        user = get_user_model().objects.create_user(
            username="offline-browser", email="offline@example.invalid"
        )
        ShopOwner.objects.create(shop=shop, user=user, email=user.email)
    owner = Client()
    owner.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    cloud_port, hub_port = port(), port()
    cloud_url = f"http://127.0.0.1:{cloud_port}"
    hub_url = f"http://127.0.0.1:{hub_port}"
    cloud_env = os.environ.copy()
    hub_env = {
        **cloud_env,
        "APP_ROLE": "hub",
        "SQLITE_PATH": str(Path(temp) / "hub.sqlite3"),
        "HUB_BRANCH_ID": str(branch.pk),
        "HUB_CLOUD_URL": cloud_url,
        "HUB_KEY": key,
        "DEVICE_SETUP_ALLOW_BROWSER": "1",
    }

    def command(*args):
        result = subprocess.run(
            [sys.executable, "manage.py", *args],
            cwd=ROOT,
            env=hub_env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)

    cloud_log = open(Path(temp) / "cloud.log", "w")
    hub_log = open(Path(temp) / "hub.log", "w")

    def start_cloud():
        proc = subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{cloud_port}",
                "--noreload",
            ],
            cwd=ROOT,
            env=cloud_env,
            stdout=cloud_log,
            stderr=cloud_log,
        )
        wait(cloud_url)
        return proc

    def cypress(base, token, role):
        if os.environ.get("RUN_CYPRESS") != "1":
            return
        result = subprocess.run(
            [
                "npx",
                "cypress",
                "run",
                "--browser",
                os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
                "--config",
                "baseUrl=" + base,
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "PATH": str(Path.home() / ".local/bin")
                + os.pathsep
                + os.environ["PATH"],
                "CYPRESS_deviceKey": token,
                "CYPRESS_paperRef": "P-7" if role == "direct" else "P-8",
            },
            capture_output=True,
            text=True,
            timeout=180,
        )
        (OUT / ("cypress-" + role + ".txt")).write_text(
            result.stdout.replace(token, "[fixture key]")
            + result.stderr.replace(token, "[fixture key]")
        )
        if result.returncode:
            raise RuntimeError("Cypress " + role + " failed; see its evidence log.")
        print("Cypress " + role + " PASS", flush=True)

    cloud = start_cloud()
    hub = None
    try:
        cypress(cloud_url, direct_key, "direct")
        with shop_context(shop):
            code, _ = issue_code(device)
            baseline = Branch.objects.get(pk=branch.pk).event_seq
        command("migrate", "--noinput")
        command("sync_hub", "--once")
        with shop_context(shop):
            activate_hub(branch, baseline)
        command("sync_hub", "--once", "--force")
        hub = subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{hub_port}",
                "--noreload",
            ],
            cwd=ROOT,
            env=hub_env,
            stdout=hub_log,
            stderr=hub_log,
        )
        wait(hub_url)
        from playwright.sync_api import sync_playwright

        with shop_context(shop):
            HubCredential.objects.filter(branch=branch).update(
                last_seen_at=timezone.now() - timedelta(minutes=31)
            )
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
                args=["--no-sandbox"],
            )
            ctx = browser.new_context(timezone_id="Asia/Manila")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(hub_url + "/device/setup/?invite=" + str(device.pk))
            page.locator("[name=code]").fill(code)
            page.get_by_role("button", name="Set up this device", exact=False).click()
            page.wait_for_url("**/jobs/new/")
            hub_key = next(
                cookie["value"]
                for cookie in ctx.cookies()
                if cookie["name"] == "washday_device"
            )
            cypress(hub_url, hub_key, "hub")
            owner_ctx = browser.new_context(timezone_id="Asia/Manila")
            owner_ctx.add_cookies(
                [
                    {
                        "name": "sessionid",
                        "value": owner.cookies["sessionid"].value,
                        "url": cloud_url,
                    }
                ]
            )
            owner_page = owner_ctx.new_page()
            original = (ROOT / "reference/prototype/index.html").read_text()
            import re

            original = re.sub(
                r'<link rel="(?:preconnect|stylesheet)"[^>]*>', "", original, count=2
            )
            original = (
                '<link rel="stylesheet" href="'
                + cloud_url
                + '/static/css/fonts.css">'
                + original
            )
            owner_ctx.route(
                cloud_url + "/__reference__",
                lambda route: route.fulfill(content_type="text/html", body=original),
            )
            owner_reference = owner_ctx.new_page()
            owner_reference.goto(cloud_url + "/__reference__")
            owner_reference.locator("[data-view=owner]").click()
            for width in (390, 1280):
                for theme in ("light", "dark"):
                    owner_page.set_viewport_size({"width": width, "height": 900})
                    owner_reference.set_viewport_size({"width": width, "height": 900})
                    owner_ctx.add_cookies(
                        [{"name": "app_theme", "value": theme, "url": cloud_url}]
                    )
                    owner_reference.evaluate(
                        "(theme)=>document.documentElement.dataset.appTheme=theme",
                        theme,
                    )
                    owner_page.goto(cloud_url + "/owner/dashboard/")
                    owner_reference.locator("[data-otab=dash]").click()
                    owner_page.get_by_role(
                        "heading", name="Branch tablets", exact=True
                    ).locator("xpath=..").screenshot(
                        path=str(OUT / f"owner-sync-{width}-{theme}.png")
                    )
                    owner_reference.get_by_role(
                        "heading", name="Branch tablets", exact=True
                    ).locator("xpath=..").screenshot(
                        path=str(OUT / f"owner-sync-reference-{width}-{theme}.png")
                    )
                    owner_page.goto(cloud_url + "/owner/live/")
                    owner_reference.locator("[data-otab=live]").click()
                    owner_reference.locator("[data-lb]").last.click()
                    assert owner_page.locator(".live-note").evaluate(
                        '(e)=>e.classList.contains("stale")'
                    )
                    owner_page.locator(".live-note").screenshot(
                        path=str(OUT / f"owner-stale-{width}-{theme}.png")
                    )
                    owner_reference.locator(".live-note").screenshot(
                        path=str(OUT / f"owner-stale-reference-{width}-{theme}.png")
                    )
            owner_ctx.close()
            # Cloud is stopped, while the hub and the device's local connection remain up.
            cloud.terminate()
            cloud.wait(timeout=10)
            totals = []
            for i in range(3):
                page.goto(hub_url + "/jobs/new/")
                page.locator("#kg").fill(str(i + 3))
                page.locator("[name=customer_name]").fill("TEST offline " + str(i))
                page.locator("[name=pay_method][value=cash]").check()
                page.locator("[data-create]").click()
                page.wait_for_url("**/jobs/*/")
                totals.append(
                    page.locator("article .total b").inner_text()
                    if page.locator("article .total b").count()
                    else page.locator("article").inner_text()
                )
            # A stock receipt and its same-device Undo work during the outage.
            page.goto(hub_url + "/supplies/")
            page.locator("[name=qty]").fill("5")
            page.get_by_role("button", name="Receive stock", exact=True).click()
            page.locator("[data-undo-until] button").click()
            assert "Action undone" in page.locator(".toast").inner_text()
            # Capture prototype/app toast pairs in both themes and viewports.
            prototype = (ROOT / "reference/prototype/index.html").read_text()
            import re

            prototype = re.sub(
                r'<link rel="(?:preconnect|stylesheet)"[^>]*>', "", prototype, count=2
            )
            prototype = prototype.replace(
                "function toast(msg, undo){",
                "window.__referenceToast=toast;\nfunction toast(msg, undo){",
            )
            prototype = (
                '<link rel="stylesheet" href="'
                + hub_url
                + '/static/css/fonts.css">'
                + prototype
            )
            ctx.route(
                hub_url + "/__reference__",
                lambda route: route.fulfill(content_type="text/html", body=prototype),
            )
            reference = ctx.new_page()
            reference.goto(hub_url + "/__reference__")
            reference.locator('[data-tab="supplies"]').click()
            for width in (390, 1280):
                for theme in ("light", "dark"):
                    page.set_viewport_size({"width": width, "height": 900})
                    reference.set_viewport_size({"width": width, "height": 900})
                    ctx.add_cookies(
                        [{"name": "app_theme", "value": theme, "url": hub_url}]
                    )
                    page.goto(hub_url + "/supplies/")
                    page.locator("[name=qty]").fill("1")
                    page.get_by_role("button", name="Receive stock", exact=True).click()
                    page.locator("[data-undo-until]").wait_for()
                    reference.evaluate(
                        "theme=>{document.documentElement.dataset.appTheme=theme;window.__referenceToast('Stock received',()=>{});}",
                        theme,
                    )
                    assert not page.evaluate(
                        "document.documentElement.scrollWidth>innerWidth"
                    )
                    page.screenshot(
                        path=str(OUT / f"undo-{width}-{theme}.png"), full_page=False
                    )
                    reference.screenshot(
                        path=str(OUT / f"undo-reference-{width}-{theme}.png"),
                        full_page=False,
                    )
                    page.locator("[data-undo-until] button").click()
            reference.close()
            assert not errors, errors
            browser.close()
        cloud = start_cloud()
        reconnect_started = time.monotonic()
        command("sync_hub", "--once", "--force")
        reconnect_seconds = time.monotonic() - reconnect_started
        assert reconnect_seconds < 60
        assert (
            b"Showing last received hub data" not in owner.get("/owner/live/").content
        )
        # Repeating a worker cycle does not duplicate collections/events.
        with shop_context(shop):
            event_ids = set(
                Event.objects.filter(branch=branch).values_list("id", flat=True)
            )
            assert (
                Job.objects.filter(
                    branch=branch, customer__name__startswith="TEST offline "
                ).count()
                == 3
            )
            actual = collections([branch], timezone.localdate())["total"]
            expected = sum(
                Job.objects.filter(branch=branch, paid_at__isnull=False).values_list(
                    "total", flat=True
                )
            )
            assert actual == expected
        command("sync_hub", "--once", "--force")
        with shop_context(shop):
            assert (
                set(Event.objects.filter(branch=branch).values_list("id", flat=True))
                == event_ids
            )
        command("sync_hub", "--retire")
        with shop_context(shop):
            final_seq = Branch.objects.get(pk=branch.pk).event_seq
            activate_direct(branch, final_seq)
        (OUT / "replication.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "databases": 2,
                    "http_servers": 2,
                    "offline_jobs": 3,
                    "collections": str(actual),
                    "event_count": len(event_ids),
                    "direct_hub_direct": "PASS",
                    "duplicate_worker": "PASS",
                    "offline_undo": "PASS",
                    "physical_router_outage": "NOT RUN",
                    "reconnect_to_owner_seconds": round(reconnect_seconds, 3),
                    "cypress_roles": "direct and hub PASS"
                    if os.environ.get("RUN_CYPRESS") == "1"
                    else "NOT RUN",
                },
                indent=2,
            )
        )
        print(
            "PASS: real HTTP bootstrap, offline jobs/Undo, replay-safe reconnect and fenced direct/hub/direct migration."
        )
    except Exception:
        # Keep local server diagnostics without emitting any runtime key.
        cloud_log.flush()
        hub_log.flush()
        for name in ("cloud", "hub"):
            text = (
                (Path(temp) / (name + ".log"))
                .read_text()
                .replace(key, "[redacted]")
                .replace(code, "[redacted]")
            )
            (OUT / (name + "-diagnostic.log")).write_text(text)
        raise
    finally:
        for process in (hub, cloud):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        cloud_log.close()
        hub_log.close()
