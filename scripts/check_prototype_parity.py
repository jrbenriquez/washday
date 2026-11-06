"""Isolated owner/staff visual and interaction checks; no public login bypass."""

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
OUT = (
    ROOT
    / ".agents/work/prototype-parity/evidence"
    / os.environ.get("EVIDENCE_RUN", "current")
)
OUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="washday-parity-") as td:
    os.environ["SQLITE_PATH"] = str(Path(td) / "db.sqlite3")
    os.environ.pop("PGDATABASE", None)
    os.environ["DJANGO_DEBUG"] = "1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone

    from catalog.models import Service, SupplyType
    from core.models import Branch, Machine, Shop, ShopOwner
    from core.tenancy import shop_context
    from jobs.services import create_job
    from jobs.transitions import advance
    from machines.models import Load
    from machines.services import start_for_job
    from people.models import Staff
    from supplies.models import SupplyRequest
    from supplies.services import count_stock

    log = io.StringIO()
    call_command("migrate", stdout=log, verbosity=0)
    call_command("seed_demo", stdout=log)
    shop = Shop.objects.get(code="DEV-ONLY")
    user = get_user_model().objects.create_user(
        username="parity-fixture", email="parity@example.invalid"
    )
    user.set_unusable_password()
    user.save()
    with shop_context(shop):
        ShopOwner.objects.create(shop=shop, user=user, email=user.email)
        branch = Branch.objects.get(code="DEMO")
        branch.simple_mode = False
        branch.save(update_fields=["simple_mode"])
        staff = Staff.objects.filter(branch=branch).first()
        service = Service.objects.filter(mode="kg", archived_at=None).first()
        jobs = []
        for n in range(4):
            job, _ = create_job(
                {
                    "service": str(service.id),
                    "kg": str(3 + n),
                    "customer_name": "DEMO parity customer " + str(n),
                    "pay_method": "cash" if n % 2 else "",
                },
                branch,
                staff,
            )
            for step in range(n):
                job = advance(
                    branch,
                    job.number,
                    str(job.status_id),
                    staff,
                    skip_reason="Labelled browser fixture",
                )
            jobs.append(job)
        washing = jobs[1]
        machine = Machine.objects.get(branch=branch, label="W1")
        start_for_job(
            branch,
            washing.number,
            str(washing.status_id),
            washing.status_id,
            machine.id,
            staff,
        )
        load = Load.objects.get(machine=machine, ended_at=None)
        load.started_at = timezone.now() - timedelta(minutes=100)
        load.save(update_fields=["started_at"])
        job = advance(
            branch,
            job.number,
            str(job.status_id),
            staff,
            skip_reason="Labelled browser fixture",
        )
        job.ready_at = timezone.now() - timedelta(days=3)
        job.save(update_fields=["ready_at"])
        count_stock(
            branch,
            {
                **{
                    "count_" + str(s.id): "12"
                    for s in SupplyType.objects.filter(archived_at=None)
                }
            },
            staff,
        )
        SupplyRequest.objects.create(
            shop=shop,
            branch=branch,
            name="DEMO Laundry sanitizer",
            note="Labelled browser fixture",
        )
    from core.models import Settings
    from people.models import Device
    from people.services import issue_code, enroll, save_staff
    from jobs.transitions import override
    with shop_context(shop):
        policy = Settings.objects.get(shop=shop)
        policy.pin_enabled = True
        policy.pin_actions = ["create", "claim", "payment", "override"]
        policy.save()
        pin_staff, _ = save_staff(branch, "DEMO modal PIN staff", "7392")
        device = Device.objects.create(shop=shop, branch=branch, name="DEMO modal tablet", kind="shared")
        code, _ = issue_code(device)
        _, device_token, error = enroll(device, code)
        assert not error
        modal_jobs = []
        for method in ["", "cash"]:
            fixture, _ = create_job({"service": str(service.id), "kg": "3", "pay_method": method}, branch, staff)
            override(branch, fixture.number, str(fixture.status_id), job.status_id, "Modal fixture", staff)
            modal_jobs.append(fixture)
    os.environ["ENABLE_DEV_BRANCH_SCOPE"] = "1"
    os.environ["DEV_BRANCH_ID"] = str(branch.id)
    os.environ["DEV_STAFF_ID"] = str(staff.id)
    settings.ENABLE_DEV_BRANCH_SCOPE = True
    settings.DEV_BRANCH_ID = str(branch.id)
    settings.DEV_STAFF_ID = str(staff.id)
    client = Client()
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    serverlog = open(Path(td) / "server.log", "w")
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=serverlog,
        stderr=serverlog,
    )
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/owner/login/", timeout=2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Fixture server did not start")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/usr/bin/chromium", args=["--no-sandbox"]
            )
            ctx = browser.new_context()
            ctx.add_cookies(
                [
                    {
                        "name": "sessionid",
                        "value": client.cookies["sessionid"].value,
                        "url": base,
                    }
                ]
            )
            page = ctx.new_page()
            page.set_default_timeout(10000)
            errors = []
            responses = []
            results = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "response",
                lambda r: (
                    responses.append({"url": r.url, "status": r.status})
                    if r.status >= 400
                    else None
                ),
            )
            reference = ctx.new_page()
            prototype = (ROOT / "reference/prototype/index.html").read_text()
            import re

            prototype = re.sub(
                r'<link rel="(?:preconnect|stylesheet)"[^>]*>', "", prototype, count=2
            )
            prototype = (
                '<link rel="stylesheet" href="'
                + base
                + '/static/css/fonts.css">'
                + prototype
            )
            ctx.route(
                base + "/__prototype__",
                lambda route: route.fulfill(content_type="text/html", body=prototype),
            )
            reference.goto(base + "/__prototype__")
            for width in [390, 1280]:
                reference.set_viewport_size({"width": width, "height": 900})
                reference.screenshot(path=str(OUT / f"reference-intake-{width}.png"), full_page=True)
            reference.locator("[data-view=owner]").click()
            for width in [360, 1280]:
                reference.set_viewport_size({"width": width, "height": 900})
                reference.screenshot(
                    path=str(OUT / f"reference-owner-{width}.png"), full_page=True
                )
            reference.close()
            paths = {
                "dashboard": "/owner/dashboard/",
                "live": "/owner/live/",
                "staff": "/owner/staff/",
                "machine-admin": "/owner/machines/",
                "settings": "/owner/settings/",
                "owner-editor": "/owner/edit/service/",
                "counts": f"/owner/counts/{branch.id}/",
                "access": "/owner/",
                "intake": "/jobs/new/",
                "board": "/jobs/",
                "list": "/jobs/?view=list",
                "history": "/jobs/?view=history",
                "timeline": f"/jobs/{job.number}/history/",
                "machines": "/machines/",
                "supplies": "/supplies/",
            }
            for name, path in ({} if os.environ.get("INTERACTIONS_ONLY") else paths).items():
                for width in [360, 390, 1280]:
                    for theme in ["light", "dark"]:
                        page.set_viewport_size({"width": width, "height": 900})
                        ctx.add_cookies(
                            [{"name": "app_theme", "value": theme, "url": base}]
                        )
                        response = page.goto(base + path)
                        assert response.status == 200, (path, response.status)
                        page.evaluate("document.fonts.ready")
                        assert not page.evaluate(
                            "document.documentElement.scrollWidth>innerWidth"
                        ), (name, width, theme)
                        assert (
                            page.locator("html").get_attribute("data-app-theme")
                            == theme
                        )
                        assert (
                            not page.locator("title").inner_text().find("<table") >= 0
                        )
                        page.screenshot(
                            path=str(OUT / f"{name}-{width}-{theme}.png"),
                            full_page=True,
                        )
                        results.append(
                            {
                                "page": name,
                                "width": width,
                                "theme": theme,
                                "overflow": False,
                            }
                        )
                print(name + " checked", flush=True)
            # Dialog composition, Escape/focus return and correct POST destination.
            page.goto(base + "/supplies/")
            count_input = page.locator("[data-count-input]").first
            count_input.fill(str(float(count_input.get_attribute("data-expected")) + 2))
            assert (
                count_input.locator("xpath=../..")
                .locator("[data-count-variance]")
                .inner_text()
                == "+2"
            )
            page.goto(base + "/jobs/new/")
            assert page.locator("[data-create]").is_disabled()
            page.locator("#kg").fill("3")
            assert page.locator("[data-create]").is_enabled()
            page.goto(base + "/owner/settings/")
            trigger = page.locator("#service a[data-dialog]").first
            trigger.click()
            page.locator("dialog[open]").wait_for()
            assert page.url == base + "/owner/settings/"
            assert (
                page.locator("dialog form").get_attribute("action")
                == base + "/owner/edit/service/"
            )
            page.keyboard.press("Escape")
            assert page.locator("dialog[open]").count() == 0
            assert trigger.evaluate("(e)=>e===document.activeElement")
            trigger.click()
            page.locator("dialog[open]").wait_for()
            page.locator("dialog [name=name]").fill("DEMO dialog owner service")
            page.locator("dialog [name=mode]").select_option("kg")
            page.locator("dialog [name=price]").fill("75")
            page.locator("dialog").get_by_role("button", name="Save changes").click()
            page.locator("dialog[open]").wait_for(state="hidden")
            assert page.locator('#service input[value="DEMO dialog owner service"]').count() == 1
            page.goto(base + "/jobs/")
            stage_link = page.locator('a[data-dialog][href$="/stage/"]').first
            stage_link.click()
            page.locator("dialog[open]").wait_for()
            for width in [360, 390, 1280]:
                page.set_viewport_size({"width": width, "height": 900})
                assert not page.evaluate(
                    "document.documentElement.scrollWidth>innerWidth"
                )
                page.screenshot(
                    path=str(OUT / f"stage-dialog-{width}.png"), full_page=True
                )
            page.locator("dialog").get_by_role(
                "radio", name="Ready", exact=True
            ).check()
            page.locator("dialog").get_by_label("Reason (optional)").fill(
                "Labelled modal fixture"
            )
            page.locator("dialog").get_by_role("button", name="Save stage").click()
            page.locator("dialog[open]").wait_for(state="hidden")
            page.get_by_role("link", name="Claim & pay", exact=True).first.click()
            page.locator("dialog[open]").wait_for()
            page.locator("dialog").get_by_role("radio", name="Cash", exact=True).check()
            page.locator("dialog").get_by_role("button", name=re.compile("Received.*Release")).click()
            page.locator("dialog[open]").wait_for(state="hidden")
            assert page.url == base + "/jobs/"
            assert "claimed." in page.locator("main .toast").inner_text()
            # Real edits through the forms, including browser validation and CSRF.
            page.goto(base + "/owner/edit/service/")
            page.locator("#id_name").fill("DEMO browser owner service")
            page.locator("#id_mode").select_option("load")
            page.locator("#id_price").fill("123.45")
            page.get_by_role("button", name="Save changes").click()
            page.wait_for_url("**/owner/settings/")
            assert page.locator('#service input[value="DEMO browser owner service"]').count() == 1
            row = page.locator("#service tr").filter(has=page.locator('input[value="DEMO browser owner service"]'))
            row.get_by_role("button", name="Remove DEMO browser owner service", exact=True).click()
            page.wait_for_url("**/owner/settings/")
            page.locator("#service .removed-items form").filter(
                has_text="DEMO browser owner service"
            ).get_by_role("button", name="Restore").click()
            page.wait_for_url("**/owner/settings/")
            page.goto(base + "/owner/live/")
            assert page.locator("#owner-live form").count() == 0
            page.goto(base + "/owner/dashboard/")
            with page.expect_download() as download:
                page.get_by_role("button", name="Export to Excel").click()
            assert download.value.suggested_filename.endswith(".xlsx")
            download.value.save_as(str(OUT / "sales.xlsx"))
            ctx.add_cookies([{"name": "app_theme", "value": "dark", "url": base}])
            page.goto(base + "/owner/settings/")
            page.get_by_role("switch", name="Dark theme").click()
            page.wait_for_load_state("networkidle")
            assert page.locator("html").get_attribute("data-app-theme") == "light"
            # Real enrolled shared device: payment -> PIN -> same board.
            pinctx = browser.new_context()
            pinctx.add_cookies([{"name": settings.DEVICE_COOKIE_NAME, "value": device_token, "url": base}])
            pinpage = pinctx.new_page()
            pinpage.on("pageerror", lambda e: errors.append(str(e)))
            for fixture in modal_jobs:
                pinpage.goto(base + "/jobs/?view=board")
                card = pinpage.locator(f'[data-job="{fixture.number}"]')
                card.get_by_role("link", name=re.compile("^Claim")).click()
                dialog = pinpage.locator("dialog[open]")
                assert not dialog.get_by_label("Release sheet date").is_visible()
                dialog.get_by_label("Released on paper").check()
                assert dialog.get_by_label("Release sheet date").is_visible()
                dialog.get_by_label("Released on paper").uncheck()
                if not fixture.paid_at:
                    dialog.get_by_role("radio", name="GCash", exact=True).check()
                    dialog.get_by_label("GCash reference (optional)").fill("DEMO-modal-ref")
                dialog.get_by_role("button", name=re.compile("Confirm claim|Received.*Release")).click()
                dialog.locator('[data-pin-form]').wait_for()
                assert pinpage.url == base + "/jobs/?view=board"
                for width in [360, 390, 1280]:
                    for theme in ["light", "dark"]:
                        pinpage.set_viewport_size({"width": width, "height": 900})
                        pinpage.evaluate("theme => document.documentElement.dataset.appTheme=theme", theme)
                        assert not pinpage.evaluate("document.documentElement.scrollWidth>innerWidth")
                        pinpage.screenshot(path=str(OUT / f"pin-{fixture.number}-{width}-{theme}.png"))
                # Cancel preserves the board and performs no write.
                pinpage.keyboard.press("Escape")
                assert card.count() == 1
                card.get_by_role("link", name=re.compile("^Claim")).click()
                if not fixture.paid_at:
                    dialog.get_by_role("radio", name="GCash", exact=True).check()
                    dialog.get_by_label("GCash reference (optional)").fill("DEMO-modal-ref")
                dialog.get_by_role("button", name=re.compile("Confirm claim|Received.*Release")).click()
                dialog.locator('[data-pin-form]').wait_for()
                for digit in "0000":
                    dialog.locator(f'[data-pin="{digit}"]').click()
                dialog.locator('[role="alert"]').filter(has_text=re.compile(".+")).wait_for()
                assert pinpage.url == base + "/jobs/?view=board"
                for digit in "7392":
                    dialog.locator(f'[data-pin="{digit}"]').click()
                dialog.wait_for(state="hidden")
                assert pinpage.url == base + "/jobs/?view=board"
                assert pinpage.locator(f'[data-job="{fixture.number}"]').count() == 0
            pinpage.goto(base + "/jobs/new/")
            pinpage.locator("#kg").fill("3")
            pinpage.locator('[data-create]').click()
            pinpage.locator('dialog [data-pin-form]').wait_for()
            for digit in "7392":
                pinpage.locator(f'dialog [data-pin="{digit}"]').click()
            pinpage.locator('dialog .stub').wait_for()
            assert pinpage.url == base + "/jobs/new/"
            pinpage.keyboard.press("Escape")
            assert pinpage.locator("#kg").input_value() == "0"
            pinctx.close()
            assert not errors, errors
            assert not responses, responses
            (OUT / "browser.json").write_text(
                json.dumps(
                    {
                        "captures": results,
                        "errors": errors,
                        "failed_responses": responses,
                        "interactions": "PASS",
                    },
                    indent=2,
                )
            )
            browser.close()
        with shop_context(shop):
            for fixture in modal_jobs:
                fixture.refresh_from_db()
                assert fixture.claimed_at and fixture.paid_at
                from events.models import Event
                assert Event.objects.get(type="job_claimed", payload__job_id=str(fixture.id)).actor_staff_id == pin_staff.id
                if fixture.pay_method == "gcash":
                    assert fixture.pay_ref == "DEMO-modal-ref"
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
