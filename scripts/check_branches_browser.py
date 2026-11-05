"""Exercise branch management against an isolated local database and owner session."""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / ".agents/work/branch-management/evidence"
    / os.environ.get("EVIDENCE_RUN", "current")
)
OUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="washday-branches-") as td:
    os.environ["SQLITE_PATH"] = str(Path(td) / "db.sqlite3")
    os.environ.pop("PGDATABASE", None)
    os.environ["DJANGO_DEBUG"] = "1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from core.models import Branch, Shop, ShopOwner
    from core.tenancy import shop_context
    from playwright.sync_api import sync_playwright

    call_command("migrate", stdout=io.StringIO(), verbosity=0)
    call_command("seed_demo", stdout=io.StringIO())
    shop = Shop.objects.get(code="DEV-ONLY")
    user = get_user_model().objects.create_user(
        username="branches-browser", email="branches@example.invalid"
    )
    with shop_context(shop):
        ShopOwner.objects.create(shop=shop, user=user, email=user.email)
        branch = Branch.objects.get(code="DEMO")
    client = Client()
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (OUT / "server.log").open("w") as serverlog:
        server = subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{port}",
                "--noreload",
            ],
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
                errors, results = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/owner/dashboard/")
                page.get_by_role("navigation", name="Owner navigation").get_by_role(
                    "link", name="Branches", exact=True
                ).click()
                assert page.url.endswith("/owner/branches/")
                assert (
                    page.get_by_role("navigation", name="Branch views")
                    .get_by_role("link", name="Live Branches")
                    .get_attribute("aria-current")
                    == "page"
                )
                page.get_by_role("link", name="Manage Branches", exact=True).click()
                page.get_by_role("link", name="Add branch", exact=True).click()
                assert page.get_by_label("Use simple workflow").is_checked()
                assert page.get_by_label("Connection mode").is_disabled()
                page.locator("#id_name").fill("DEMO North branch")
                page.locator("#id_code").fill("NORTH")
                page.locator("#id_opening_time").fill("08:00")
                page.locator("#id_closing_time").fill("20:00")
                page.get_by_role("button", name="Add branch", exact=True).click()
                page.wait_for_url("**/owner/branches/manage/")
                card = page.locator(".branch-card").filter(
                    has=page.get_by_role(
                        "heading", name="DEMO North branch", exact=True
                    )
                )
                card.get_by_role(
                    "link", name="Edit DEMO North branch", exact=True
                ).click()
                page.locator("#id_name").fill("DEMO Renamed North branch")
                page.get_by_label("Use simple workflow").uncheck()
                page.get_by_role("button", name="Save branch", exact=True).click()
                page.wait_for_url("**/owner/branches/manage/")
                card = page.locator(".branch-card").filter(
                    has=page.get_by_role(
                        "heading", name="DEMO Renamed North branch", exact=True
                    )
                )
                assert "Full workflow" in card.inner_text()
                card.get_by_role(
                    "link", name="View DEMO Renamed North branch live", exact=True
                ).click()
                assert page.get_by_role(
                    "heading", name="DEMO Renamed North branch right now"
                ).is_visible()
                assert (
                    page.locator("#owner-live").get_attribute("hx-trigger")
                    == "every 20s"
                )
                assert page.locator("#owner-live button, #owner-live form").count() == 0
                page.get_by_role("link", name="Edit branch", exact=True).click()
                edit_path = page.url.removeprefix(base)
                # Server-side duplicate validation leaves the editor and submitted fields intact.
                page.locator("#id_code").fill("DEMO")
                page.get_by_role("button", name="Save branch", exact=True).click()
                assert page.get_by_text(
                    "A branch with this code already exists in your shop."
                ).is_visible()
                assert (
                    page.locator("#id_name").input_value()
                    == "DEMO Renamed North branch"
                )
                created_id = edit_path.split("/")[3]
                paths = {
                    "manage": "/owner/branches/manage/",
                    "new": "/owner/branches/new/",
                    "edit": edit_path,
                    "live": f"/owner/branches/?branch={created_id}",
                    "live-legacy": f"/owner/live/?branch={branch.id}",
                    "settings": "/owner/settings/",
                    "access": "/owner/",
                }
                for name, path in paths.items():
                    for width in (360, 1280):
                        for theme in ("light", "dark"):
                            page.set_viewport_size({"width": width, "height": 900})
                            ctx.add_cookies(
                                [{"name": "app_theme", "value": theme, "url": base}]
                            )
                            response = page.goto(base + path)
                            assert response.status == 200, (name, response.status)
                            page.evaluate("document.fonts.ready")
                            assert not page.evaluate(
                                "document.documentElement.scrollWidth > innerWidth"
                            ), (name, width, theme)
                            assert (
                                page.locator("html").get_attribute("data-app-theme")
                                == theme
                            )
                            if name in ("manage", "new", "edit", "live", "live-legacy"):
                                assert (
                                    page.get_by_role(
                                        "navigation", name="Owner navigation"
                                    )
                                    .get_by_role("link", name="Branches", exact=True)
                                    .get_attribute("aria-current")
                                    == "page"
                                )
                            if name in ("manage", "new", "edit", "live"):
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
                # Observe the live endpoint's actual timer request without changing the product interval.
                page.goto(base + f"/owner/branches/?branch={created_id}")
                with page.expect_response(
                    lambda r: "/owner/branches/?branch=" in r.url
                    and r.request.headers.get("hx-request") == "true",
                    timeout=25000,
                ) as refresh:
                    pass
                assert refresh.value.status == 200
                assert not errors, errors
                (OUT / "results.json").write_text(
                    json.dumps(
                        {
                            "status": "PASS",
                            "pages": results,
                            "interactions": [
                                "navigation",
                                "create",
                                "edit",
                                "live shortcut",
                                "duplicate validation",
                                "read-only board",
                                "20-second refresh",
                            ],
                            "page_errors": errors,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                browser.close()
                print(
                    f"PASS: {len(results)} page/theme/viewport checks; create/edit, duplicate validation, live shortcuts and actual timed refresh."
                )
        finally:
            server.terminate()
            server.wait(timeout=10)
