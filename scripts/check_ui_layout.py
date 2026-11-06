"""Capture UI audit evidence using an isolated SQLite fixture and owner session."""

import argparse
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
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--phase", choices=["before", "after"], required=True)
args = parser.parse_args()
OUT = ROOT / "docs/ui-audit" / args.phase
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
            paths = {
                "dashboard": "/owner/dashboard/",
                "live": "/owner/live/",
                "branches": "/owner/branches/manage/",
                "branch-editor": f"/owner/branches/{branch.id}/edit/",
                "staff": "/owner/staff/",
                "machine-admin": "/owner/machines/",
                "settings": "/owner/settings/",
                "owner-editor": "/owner/edit/service/",
                "counts": f"/owner/counts/{branch.id}/",
                "access": "/owner/",
                "intake": "/jobs/new/",
                "paper": "/jobs/new/?paper=1",
                "board": "/jobs/",
                "list": "/jobs/?view=list",
                "history": "/jobs/?view=history",
                "timeline": f"/jobs/{job.number}/history/",
                "stub": f"/jobs/{job.number}/",
                "machines": "/machines/",
                "supplies": "/supplies/",
            }
            # Keep the reviewable image set small; inspect all routes at every size.
            pictured = {"dashboard", "intake", "board", "settings", "supplies",
                        "branches", "staff", "machines", "access"}
            for name, path in paths.items():
                for width in [360, 390, 768, 1280]:
                    for theme in ["light", "dark"]:
                        page.set_viewport_size({"width": width, "height": 900})
                        ctx.add_cookies([{"name": "app_theme", "value": theme, "url": base}])
                        response = page.goto(base + path)
                        assert response.status == 200, (name, width, theme, response.status)
                        page.evaluate("document.fonts.ready")
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (name, width, theme)
                        assert page.locator("html").get_attribute("data-app-theme") == theme
                        if args.phase == "after" and name == "settings" and width < 760:
                            # Responsive catalog cells must not collide, even when their
                            # table wrapper would otherwise conceal the overflow.
                            assert page.locator(".settings-section .edit-table tr").evaluate_all("""rows => rows.every(row => {
                                const rects = [...row.children].map(e => e.getBoundingClientRect());
                                return rects.every((a, i) => rects.slice(i + 1).every(b =>
                                    Math.min(a.right,b.right)-Math.max(a.left,b.left) < 1 ||
                                    Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top) < 1));
                            })"""), (name, width, theme, "overlapping catalog cells")
                        if args.phase == "after" and name == "board" and width == 1280:
                            assert page.locator(".board").evaluate("e => e.scrollWidth <= e.clientWidth"), "Five stages should fit on desktop"
                        if name in pictured and (width, theme) in [(1280, "light"), (390, "dark")]:
                            page.screenshot(path=str(OUT / f"{name}-{width}-{theme}.png"), full_page=True)
                        results.append({"page": name, "width": width, "theme": theme, "overflow": False})
                print(name + " checked", flush=True)
            # Native dialog opening, keyboard dismissal and focus restoration.
            ctx.add_cookies([{"name": "app_theme", "value": "light", "url": base}])
            page.goto(base + "/jobs/")
            trigger = page.locator('a[data-dialog][href$="/stage/"]').first
            trigger.click()
            page.locator("dialog[open]").wait_for()
            page.screenshot(path=str(OUT / "stage-dialog-1280-light.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 900})
            page.evaluate("document.documentElement.dataset.appTheme = 'dark'")
            page.screenshot(path=str(OUT / "stage-dialog-390-dark.png"), full_page=True)
            page.keyboard.press("Escape")
            assert page.locator("dialog[open]").count() == 0
            assert trigger.evaluate("e => e === document.activeElement")
            signed_out = browser.new_context()
            login = signed_out.new_page()
            for width, theme in [(1280, "light"), (390, "dark")]:
                login.set_viewport_size({"width": width, "height": 900})
                signed_out.add_cookies([{"name": "app_theme", "value": theme, "url": base}])
                assert login.goto(base + "/owner/login/").status == 200
                login.evaluate("document.fonts.ready")
                assert not login.evaluate("document.documentElement.scrollWidth > innerWidth")
                login.screenshot(path=str(OUT / f"login-{width}-{theme}.png"), full_page=True)
                results.append({"page": "login", "width": width, "theme": theme, "overflow": False})
            signed_out.close()
            assert not errors, errors
            assert not responses, responses
            (OUT / "checks.json").write_text(json.dumps({"layouts": results, "errors": errors, "failed_responses": responses, "dialog_focus": "PASS"}, indent=2) + "\n")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
