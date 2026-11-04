"""Isolated owner catalog UI probe; no public login bypass or real Google request."""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / ".agents/work/owner-settings/evidence"
    / os.environ.get("EVIDENCE_RUN", "catalog-1")
)
if OUT.exists():
    raise SystemExit("Choose a new EVIDENCE_RUN; existing evidence is retained.")
OUT.mkdir(parents=True)
with tempfile.TemporaryDirectory(prefix="washday-auth-browser-") as td:
    os.environ["SQLITE_PATH"] = str(Path(td) / "db.sqlite3")
    os.environ.pop("PGDATABASE", None)
    os.environ["DJANGO_DEBUG"] = "1"
    os.environ["ENABLE_DEV_BRANCH_SCOPE"] = "0"
    os.environ["DEVICE_SETUP_ALLOW_BROWSER"] = "1"
    os.environ["GOOGLE_CLIENT_ID"] = "browser-fixture-client"
    os.environ["GOOGLE_CLIENT_SECRET"] = "browser-fixture-secret"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.test import Client
    from core.models import Shop, ShopOwner
    from core.tenancy import shop_context

    log = io.StringIO()
    call_command("migrate", stdout=log, verbosity=0)
    call_command("seed_demo", stdout=log)
    call_command(
        "allow_owner", "browser-owner@example.invalid", shop_code="DEV-ONLY", stdout=log
    )
    shop = Shop.objects.get(code="DEV-ONLY")
    user = get_user_model().objects.create_user(
        username="browser-fixture-owner", email="browser-owner@example.invalid"
    )
    user.set_unusable_password()
    user.save()
    with shop_context(shop):
        own = ShopOwner.objects.get(email=user.email)
        own.user = user
        own.save(update_fields=["user"])
    # Only this private probe process constructs the fixture owner session.
    owner_client = Client()
    owner_client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    session = owner_client.cookies["sessionid"].value
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
        import urllib.request

        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/owner/login/", timeout=2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Private auth server did not start")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/usr/bin/chromium", args=["--no-sandbox"]
            )
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_cookies([{"name": "sessionid", "value": session, "url": base}])
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/owner/settings/")
            from playwright.sync_api import expect

            minimum = page.get_by_label("Minimum kilos")
            minimum.fill("4.5")
            minimum.press("Tab")
            expect(
                page.locator("#operational-settings").get_by_role("status")
            ).to_have_text("Saved")
            page.reload()
            expect(page.get_by_label("Minimum kilos")).to_have_value("4.5")

            # Inline edits persist through reload, without leaving the page.
            service = page.locator("#service tbody tr").first
            price = service.locator('input[name="price"]')
            price.fill("123.45")
            price.press("Tab")
            expect(service.get_by_role("status")).to_have_text("Saved")
            page.reload()
            expect(page.locator('#service input[name="price"]').first).to_have_value(
                "123.45"
            )
            fee = page.locator("#fee tbody tr").first
            fee.locator('input[name="note"]').fill("Same day, edited")
            fee.locator('input[name="note"]').press("Tab")
            expect(fee.get_by_role("status")).to_have_text("Saved")

            # New piece item includes a first price; + Size pins its parent.
            page.get_by_role("link", name="+ Add piece item", exact=True).click()
            dialog = page.get_by_role("dialog")
            dialog.get_by_label("Name").fill("Browser bedsheet")
            dialog.get_by_label("Price (₱)").fill("150")
            dialog.get_by_role("button", name="Save changes").click()
            row = (
                page.locator("#piece tbody tr")
                .filter(has_text="Browser bedsheet")
                .first
            )
            expect(row).to_contain_text("Each")
            row.get_by_role("link", name="+ Size", exact=True).click()
            dialog = page.get_by_role("dialog")
            expect(dialog.get_by_label("Piece item")).to_be_disabled()
            dialog.get_by_label("Label").fill("King")
            dialog.get_by_label("Price (₱)").fill("250")
            dialog.get_by_role("button", name="Save changes").click()
            expect(page.locator("#piece")).to_contain_text("Regular")
            expect(page.locator("#piece")).to_contain_text("King")
            row = page.locator("#piece tbody tr").filter(has_text="King").last
            row.get_by_role(
                "button", name="Remove size King for Browser bedsheet", exact=True
            ).click()
            expect(page.locator("#piece")).to_contain_text(
                "Removed sizes for Browser bedsheet"
            )
            page.locator("#piece .removed-items form").filter(
                has_text="King"
            ).get_by_role("button", name="Restore").click()

            # Add-on recipes appear as removable supply chips and retain quantity.
            addon = page.locator("#addon tbody tr").first
            addon.get_by_role("link", name="+ Supply", exact=True).click()
            dialog = page.get_by_role("dialog")
            expect(dialog.get_by_label("Addon")).to_be_disabled()
            supply = dialog.get_by_label("Supply type")
            option = supply.locator("option").last
            supply_name = option.inner_text()
            supply.select_option(option.get_attribute("value"))
            dialog.get_by_label("Quantity used per job").fill("2.5")
            dialog.get_by_role("button", name="Save changes").click()
            expect(
                page.locator("#addon .use-chip").filter(has_text=supply_name).first
            ).to_contain_text("2.5")

            supply_row = page.locator("#supply tbody tr").first
            supply_row.locator('input[name="low_level"]').fill("13.5")
            supply_row.locator('input[name="low_level"]').press("Tab")
            expect(supply_row.get_by_role("status")).to_have_text("Saved")
            toggle = page.locator("#supply").get_by_role("switch")
            was_enabled = toggle.get_attribute("aria-checked")
            toggle.click()
            expect(page.locator("#supply").get_by_role("switch")).to_have_attribute(
                "aria-checked", "false" if was_enabled == "true" else "true"
            )

            # Archive/restore a piece without losing its sizes or prices.
            row = (
                page.locator("#piece tbody tr")
                .filter(has_text="Browser bedsheet")
                .first
            )
            row.get_by_role("button", name="Archive", exact=True).click()
            page.locator("#piece > .removed-items form").filter(
                has_text="Browser bedsheet"
            ).get_by_role("button", name="Restore").click()
            expect(page.locator("#piece")).to_contain_text("King")
            for width in (1280, 768, 390):
                page.set_viewport_size({"width": width, "height": 900})
                for theme in ("light", "dark"):
                    ctx.add_cookies(
                        [{"name": "app_theme", "value": theme, "url": base}]
                    )
                    page.reload()
                    page.screenshot(
                        path=str(OUT / f"settings-{width}-{theme}.png"), full_page=True
                    )
                    assert not page.evaluate(
                        "document.documentElement.scrollWidth > innerWidth"
                    ), (width, theme)
            assert not errors, errors
            # All forms remain usable without JavaScript.
            plain = browser.new_context(java_script_enabled=False)
            plain.add_cookies([{"name": "sessionid", "value": session, "url": base}])
            fallback = plain.new_page()
            fallback.goto(base + "/owner/settings/")
            row = fallback.locator("#fee tbody tr").first
            row.locator('input[name="amount"]').fill("75")
            row.get_by_role("button", name="Save", exact=True).click()
            expect(fallback.locator('#fee input[name="amount"]').first).to_have_value(
                "75.00"
            )
            browser.close()
            (OUT / "result.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "viewports": [1280, 768, 390],
                        "themes": ["light", "dark"],
                        "javascript_errors": errors,
                    },
                    indent=2,
                )
            )
            print(OUT)
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
