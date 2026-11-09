from urllib.parse import parse_qs, urlsplit

"""Isolated authentication UI probe; no public login bypass or real Google request."""

import io, json, os, re, socket, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / ".agents/work/personal-device-binding/evidence"
    / os.environ.get("EVIDENCE_RUN", "browser-1")
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
    from core.models import Shop, ShopOwner, Branch
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
            errors = []
            external = []

            def context():
                c = browser.new_context()
                c.on(
                    "page",
                    lambda page: page.on("pageerror", lambda e: errors.append(str(e))),
                )

                def route(r):
                    if r.request.url.startswith(base + "/"):
                        r.continue_()
                    else:
                        external.append(r.request.url)
                        r.abort()

                c.route("**/*", route)
                return c

            owner_ctx = context()
            owner_ctx.add_cookies(
                [{"name": "sessionid", "value": session, "url": base}]
            )
            owner_page = owner_ctx.new_page()
            owner_page.goto(base + "/owner/staff/")
            for name, pin in [("TEST phone owner", "1234"), ("TEST other staff", "5678")]:
                form = owner_page.locator('form[action="/owner/staff/new/"]')
                form.get_by_label("Staff name").fill(name)
                form.get_by_label("Four-digit PIN").fill(pin)
                form.get_by_role("button", name="Add staff").click()
                owner_page.get_by_role("link", name="Back to staff").click()
            owner_page.goto(base + "/owner/")
            form = owner_page.locator('form[action="/owner/devices/new/"]')
            form.get_by_label("Device name").fill("TEST personal phone")
            form.get_by_label("Device type").select_option("personal")
            form.get_by_label("Assigned staff").select_option(label="TEST phone owner · DEMO branch · not operating data")
            form.get_by_role("button", name="Create setup invitation").click()
            code = owner_page.get_by_label("Six-digit setup code").inner_text()
            url = owner_page.get_by_role("link", name="Open installation page").get_attribute("href")
            invite = parse_qs(urlsplit(url).query)["invite"][0]
            phone_ctx = context()
            phone = phone_ctx.new_page()
            phone.goto(url)
            phone.get_by_role("link", name="Continue to setup").click()
            phone.get_by_label("Six-digit setup code").fill(code)
            phone.get_by_role("button", name="Set up this device").click()
            phone.wait_for_url("**/shift/")
            assert phone.locator('select[name="staff"]').count() == 0
            assert "TEST phone owner" in phone.locator("main").inner_text()
            assert "TEST other staff" not in phone.locator("main").inner_text()
            phone.get_by_label("Four-digit PIN").fill("5678")
            phone.get_by_role("button", name="Sign in", exact=True).click()
            assert "The PIN is not valid" in phone.get_by_role("alert").inner_text()
            phone.get_by_label("Four-digit PIN").fill("1234")
            phone.get_by_role("button", name="Sign in", exact=True).click()
            phone.wait_for_url("**/jobs/")
            assert "TEST phone owner" in phone.locator(".identity").inner_text()
            phone.get_by_role("button", name="Sign out", exact=True).click()
            phone.wait_for_url("**/shift/")
            # Simulate opening the saved home-screen launch URL after sign-out.
            phone.goto(base + "/device/setup/?invite=" + invite)
            phone.wait_for_url("**/shift/")
            for width in (390, 1280):
                phone.set_viewport_size({"width": width, "height": 900})
                assert not phone.evaluate("document.documentElement.scrollWidth>innerWidth")
                phone.screenshot(path=str(OUT / f"pin-only-{width}.png"), full_page=True)
            owner_page.goto(base + "/owner/")
            tile = owner_page.locator("section", has=owner_page.get_by_role("heading", name="TEST personal phone", exact=True))
            tile.get_by_text("Assign staff", exact=True).click()
            tile.get_by_label("Assigned staff").select_option(label="TEST other staff · DEMO branch · not operating data")
            tile.get_by_role("button", name="Save assignment and get setup code").click()
            new_code = owner_page.get_by_label("Six-digit setup code").inner_text()
            phone.goto(base + "/jobs/")
            phone.wait_for_url("**/device/setup/")
            phone.goto(base + "/device/setup/?invite=" + invite)
            phone.get_by_label("Six-digit setup code").fill(new_code)
            phone.get_by_role("button", name="Set up this device").click()
            phone.wait_for_url("**/shift/")
            assert "TEST other staff" in phone.locator("main").inner_text()
            phone.get_by_label("Four-digit PIN").fill("1234")
            phone.get_by_role("button", name="Sign in", exact=True).click()
            assert "The PIN is not valid" in phone.get_by_role("alert").inner_text()
            phone.get_by_label("Four-digit PIN").fill("5678")
            phone.get_by_role("button", name="Sign in", exact=True).click()
            phone.wait_for_url("**/jobs/")
            assert "TEST other staff" in phone.locator(".identity").inner_text()
            assert not external and not errors, (external, errors)
            (OUT / "browser.json").write_text(json.dumps({
                "status": "PASS", "flows": [
                    "owner provisions assigned personal phone", "PIN-only sign-in",
                    "another staff PIN rejected", "saved shortcut retains assignment",
                    "owner reassignment revokes existing credential",
                    "fresh setup accepts only newly assigned staff PIN",
                ], "external_requests": external, "javascript_errors": errors,
            }, indent=2) + "\n")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
print("Personal device binding browser PASS")
