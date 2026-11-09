"""Record onboarding and probe branch validation using a temporary local shop.

Google consent is outside this check: the recording intercepts only the local
Google-login POST and installs a Django test session. No app auth bypass is added.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs/ui-audit/onboarding-branch"
OUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="washday-onboarding-") as temporary:
    os.environ.update(SQLITE_PATH=str(Path(temporary) / "db.sqlite3"),
                      DJANGO_DEBUG="1", DJANGO_SETTINGS_MODULE="config.settings",
                      DEVICE_SETUP_ALLOW_BROWSER="1", DJANGO_ALLOW_ASYNC_UNSAFE="true",
                      GOOGLE_CLIENT_ID="browser-fixture", GOOGLE_CLIENT_SECRET="browser-fixture")
    os.environ.pop("PGDATABASE", None)
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client
    from core.models import Branch, Shop, ShopOwner
    from core.tenancy import shop_context
    from people.models import Device
    from playwright.sync_api import sync_playwright

    call_command("migrate", stdout=io.StringIO(), verbosity=0)
    call_command("create_shop", shop_code="ONBOARDING-TEST", name="Laundry demo",
                 min_kg="3", kg_per_load="7", interactive=False, stdout=io.StringIO())
    shop = Shop.objects.get(code="ONBOARDING-TEST")
    user = get_user_model().objects.create_user(username="onboarding-demo", email="demo@example.invalid")
    with shop_context(shop):
        ShopOwner.objects.create(shop=shop, user=user, email=user.email)
    client = Client()
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    session = client.cookies["sessionid"].value
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    serverlog = (Path(temporary) / "server.log").open("w")
    server = subprocess.Popen([sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
                              cwd=ROOT, stdout=serverlog, stderr=serverlog, env=os.environ.copy())
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/health/", timeout=2).close()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("Fixture server did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1280, "height": 900},
                                          record_video_dir=str(Path(temporary) / "video"),
                                          record_video_size={"width": 1280, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def test_login(route):
                context.add_cookies([{"name": "sessionid", "value": session, "url": base}])
                route.fulfill(status=302, headers={"Location": base + "/owner/onboarding/"}, body="")

            page.route("**/accounts/google/login/", test_login)
            page.goto(base + "/")
            page.wait_for_timeout(1800)
            page.get_by_role("link", name="Owner sign-in", exact=True).click()
            page.wait_for_timeout(1800)
            page.get_by_role("button", name="Continue with Google").click()
            page.wait_for_url("**/owner/onboarding/")
            page.wait_for_timeout(1500)
            page.locator('[name="services-0-price"]').fill("35")
            page.locator('[name="services-1-price"]').fill("30")
            page.locator('[name="pieces-0-price"]').fill("5")
            page.get_by_label("Minimum kilos allowed").fill("3")
            page.get_by_label("Maximum kilos per load").fill("7")
            page.wait_for_timeout(1500)
            page.get_by_role("button", name="Save and continue").click()
            page.wait_for_url("**/owner/onboarding/branch/")
            assert page.get_by_label("Branch code").input_value() == "ONE"
            assert page.get_by_label("Use simple workflow").is_checked()
            page.wait_for_timeout(1800)
            page.get_by_label("Branch name").fill("Main Branch")
            page.get_by_label("Opening time").fill("08:00")
            page.get_by_label("Closing time").fill("20:00")
            page.wait_for_timeout(1800)
            page.screenshot(path=str(OUT / "branch-desktop.png"), full_page=True)
            page.get_by_role("button", name="Save branch and continue").click()
            page.wait_for_url("**/owner/onboarding/device/")
            assert "Main Branch" in page.locator("main").inner_text()
            page.wait_for_timeout(1800)
            page.get_by_role("button", name="Set up shared device").click()
            page.wait_for_url("**/owner/?branch=**")
            assert page.get_by_label("Device name").input_value() == "Main Branch counter"
            assert page.get_by_label("Device type").input_value() == "shared"
            page.wait_for_timeout(1800)
            page.get_by_role("button", name="Create setup invitation").click()
            page.get_by_label("Six-digit setup code").wait_for()
            page.wait_for_timeout(1800)
            page.screenshot(path=str(OUT / "device-invitation.png"), full_page=True)
            setup_code = page.get_by_label("Six-digit setup code").inner_text().strip()
            page.get_by_role("link", name="Open installation page").click()
            page.wait_for_timeout(1500)
            page.get_by_role("link", name="Continue to setup").click()
            page.get_by_label("Six-digit setup code").fill(setup_code)
            page.wait_for_timeout(1500)
            page.get_by_role("button", name="Set up this device", exact=True).click()
            page.wait_for_url("**/jobs/new/")
            page.wait_for_timeout(1500)
            page.goto(base + "/owner/")
            assert "Enrolled" in page.locator("main").inner_text()
            assert "Main Branch counter" in page.locator("main").inner_text()
            page.wait_for_timeout(1800)
            video = page.video
            context.close()
            video.save_as(str(OUT / "flow.webm"))
            subprocess.run(["ffmpeg", "-y", "-i", str(OUT / "flow.webm"),
                            "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(OUT / "flow.mp4")],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (OUT / "flow.webm").unlink()
            assert Device.unscoped.filter(shop=shop, branch__code="ONE", kind="shared").exclude(key_hash="").count() == 1
            shop.refresh_from_db()
            assert shop.onboarding_completed_at
            print("Recorded homepage → sign-in → shop → branch → shared-device enrollment; Google consent stubbed")

            # Reopen only the temporary shop for visual and validation checks.
            Shop.objects.filter(pk=shop.pk).update(onboarding_completed_at=None)
            with shop_context(shop):
                Branch.objects.create(shop=shop, number=2, name="Other branch", code="TAKEN")
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_cookies([{"name": "sessionid", "value": session, "url": base}])
            page = ctx.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            Shop.objects.filter(pk=shop.pk).update(onboarding_catalog_saved_at=None)
            page.goto(base + "/owner/onboarding/")
            for group_name in ["services", "pieces"]:
                group = page.locator(f'[data-onboarding-group="{group_name}"]')
                group.locator('[data-add-row]').focus()
                page.keyboard.press("Enter")
                row = group.locator('[data-onboarding-row]').last
                assert row.locator('[name$="-name"]').evaluate("el => el === document.activeElement")
                row.locator('[name$="-name"]').fill("Extra item")
                row.locator('[data-remove-row]').focus()
                page.keyboard.press("Enter")
                assert "is-removed" in row.get_attribute("class")
                page.keyboard.press("Enter")
                assert "is-removed" not in row.get_attribute("class")
                assert row.locator('[name$="-name"]').input_value() == "Extra item"
            Shop.objects.filter(pk=shop.pk).update(onboarding_catalog_saved_at=shop.onboarding_catalog_saved_at)
            page.goto(base + "/owner/onboarding/branch/")
            page.get_by_label("Branch code").fill("taken")
            page.get_by_role("button", name="Save branch and continue").click()
            assert "already exists in your shop" in page.locator("main").inner_text()
            assert page.get_by_label("Branch code").input_value() == "taken"
            assert page.get_by_label("Branch name").input_value() == "Main Branch"
            assert page.locator("[data-error-summary]").evaluate("el => el === document.activeElement")
            assert page.get_by_label("Branch code").get_attribute("aria-invalid") == "true"
            descriptions = page.get_by_label("Branch code").get_attribute("aria-describedby").split()
            assert all(page.locator(f'[id="{value}"]').count() for value in descriptions)
            page.screenshot(path=str(OUT / "branch-duplicate-error.png"), full_page=True)
            page.goto(base + "/owner/onboarding/device/")
            assert page.url.endswith("/owner/onboarding/branch/")
            print("Duplicate code is case-insensitive, inline, retains values and blocks device step")

            # Every viewport/theme screenshot uses the current server-rendered branch form.
            contrast = []
            for theme in ["light", "dark"]:
                ctx.add_cookies([{"name": "app_theme", "value": theme, "url": base}])
                for width in [320, 390, 620, 768, 1280]:
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(base + "/owner/onboarding/branch/")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.get_by_label("Branch name").focus()
                    page.keyboard.press("Tab")
                    assert page.get_by_label("Branch code").evaluate("el => el === document.activeElement")
                    assert page.get_by_label("Branch code").evaluate("el => getComputedStyle(el).outlineStyle !== 'none'")
                    if width == 320:
                        assert page.get_by_label("Branch name").evaluate("el => parseFloat(getComputedStyle(el).fontSize) >= 16")
                    page.evaluate("scrollTo(0, 0)")
                    page.screenshot(path=str(OUT / f"branch-{width}-{theme}.png"), full_page=True)
                samples = page.evaluate('''() => {
                    const bg = el => { for (; el; el = el.parentElement) {
                        const c = getComputedStyle(el).backgroundColor;
                        if (c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c;
                    } return 'rgb(255, 255, 255)'; };
                    return ['h1', '.onboarding-heading p', '.onboarding-section-heading p',
                            '.field label', '.field small', '.field input', '.onboarding-help',
                            '.onboarding-footer p', '.onboarding-footer .primary'].map(s => {
                        const el = document.querySelector(s), c = getComputedStyle(el);
                        return {selector:s, foreground:c.color, background:bg(el), border:c.borderTopColor,
                                outline:c.outlineColor};
                    });
                }''')
                contrast.append({"theme": theme, "samples": samples})
                page.set_viewport_size({"width": 320, "height": 900})
                page.evaluate("document.documentElement.dir='rtl'")
                page.screenshot(path=str(OUT / f"branch-rtl-{theme}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.set_viewport_size({"width": 1280, "height": 900})
                page.evaluate("document.documentElement.dir='ltr'; document.documentElement.style.zoom='2'")
                page.screenshot(path=str(OUT / f"branch-zoom-{theme}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.evaluate("document.documentElement.style.zoom='1'; document.querySelector('label[for=id_name]').textContent='Branch name with an unusually long descriptive translated label'")
                page.set_viewport_size({"width": 320, "height": 900})
                page.screenshot(path=str(OUT / f"branch-long-label-{theme}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            (OUT / "contrast.json").write_text(json.dumps(contrast, indent=2))
            page.emulate_media(reduced_motion="reduce")
            assert page.locator(".onboarding-footer .primary").evaluate("el => getComputedStyle(el).transitionDuration") == "0s"
            page.get_by_label("Branch code").fill("CUSTOM")
            page.get_by_label("Use simple workflow").uncheck()
            page.get_by_role("button", name="Save branch and continue").focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/owner/onboarding/device/")
            branch = Branch.unscoped.filter(shop=shop, number=1).get()
            assert branch.code == "CUSTOM" and not branch.simple_mode
            assert not errors, errors
            ctx.close()
            browser.close()
            print("Light/dark 320/390/620/768/1280px; keyboard/focus; RTL; 200% CSS zoom; long labels; reduced motion; override saved")
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
