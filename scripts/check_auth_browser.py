from urllib.parse import parse_qs, urlsplit

"""Isolated authentication UI probe; no public login bypass or real Google request."""

import io, json, os, re, socket, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / ".agents/work/local-authentication/evidence"
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
            owner_page.goto(base + "/owner/")
            assert (
                "access and devices"
                in owner_page.locator("h2").first.inner_text().casefold()
            )
            hours = owner_page.locator('form[action$="/hours/"]').first
            hours.get_by_label("Opening time").fill("08:00")
            hours.get_by_label("Closing time").fill("23:59")
            hours.get_by_role("button", name="Save hours").click()
            owner_page.get_by_role("link", name="Staff", exact=True).click()
            add_staff = owner_page.locator('form[action="/owner/staff/new/"]')
            add_staff.get_by_label("Staff name").fill("TEST browser staff")
            add_staff.get_by_label("Four-digit PIN").fill("1234")
            add_staff.get_by_role("button", name="Add staff").click()
            assert (
                owner_page.locator('[aria-label="New staff PIN"]').inner_text()
                == "1234"
            )
            owner_page.get_by_role("link", name="Back to staff").click()

            def capture(page, view):
                for width in [360, 390, 1280]:
                    page.set_viewport_size({"width": width, "height": 900})
                    for theme in ["light", "dark"]:
                        page.context.add_cookies(
                            [{"name": "app_theme", "value": theme, "url": base}]
                        )
                        page.reload()
                        assert not page.evaluate(
                            "document.documentElement.scrollWidth>innerWidth"
                        ), (view, width, theme)
                        page.screenshot(
                            path=str(OUT / f"{view}-{width}-{theme}.png"),
                            full_page=True,
                        )

            capture(owner_page, "owner-staff")
            owner_page.get_by_role("link", name="Access and devices", exact=True).first.click()
            capture(owner_page, "owner-access")
            assert not owner_page.locator('form[action^="/owner/staff/"]').count()
            assert not owner_page.locator('form[action="/owner/pin-rules/"]').count()
            owner_page.get_by_role("link", name="Settings", exact=True).click()
            policy = owner_page.locator('form[action="/owner/pin-rules/"]')
            assert policy.count() == 1
            policy.get_by_role("button", name="Save PIN rules").click()
            owner_page.wait_for_url("**/owner/settings/")
            capture(owner_page, "owner-settings")

            def create_device(name, kind):
                owner_page.goto(base + "/owner/")
                form = owner_page.locator('form[action="/owner/devices/new/"]')
                form.get_by_label("Device name").fill(name)
                form.get_by_label("Device type").select_option(kind)
                form.get_by_role("button", name="Create setup invitation").click()
                owner_page.locator("#install-qr svg").wait_for()
                assert owner_page.locator("#install-qr svg").count() == 1
                code = owner_page.locator(
                    '[aria-label="Six-digit setup code"]'
                ).inner_text()
                url = owner_page.get_by_role(
                    "link", name="Open installation page"
                ).get_attribute("href")
                return code, url

            code, url = create_device("TEST browser counter", "shared")
            staff_ctx = context()
            staff_page = staff_ctx.new_page()
            staff_page.goto(url)
            assert not any(c["name"] == "washday_device" for c in staff_ctx.cookies())
            staff_page.get_by_role("link", name="Continue to setup").click()
            capture(staff_page, "setup")
            staff_page.get_by_label("Six-digit setup code").fill(code)
            staff_page.get_by_role(
                "button", name="Set up this device", exact=True
            ).click()
            staff_page.wait_for_url("**/jobs/new/")
            cookie = next(
                c for c in staff_ctx.cookies() if c["name"] == "washday_device"
            )
            assert cookie["httpOnly"] and cookie["sameSite"] == "Lax"
            staff_page.get_by_label("DEMO Wash-dry-fold").check()
            staff_page.get_by_label("Clothes weight (kg)").fill("2")
            staff_page.get_by_role("button", name="Create job & show stub").click()
            staff_page.wait_for_url(re.compile(r".*/jobs/\d+/"))
            number = int(staff_page.url.rstrip("/").split("/")[-1])
            assert "TEST browser counter" in staff_page.locator("article").inner_text()
            staff_page.goto(base + "/jobs/")
            staff_page.locator(f'[data-job="{number}"]').get_by_role(
                "button", name=re.compile(r"Move job .* to Ready")
            ).click()
            staff_page.locator(f'[data-job="{number}"]').get_by_role(
                "link", name="Claim & pay", exact=True
            ).click()
            staff_page.get_by_label("Payment method").select_option("cash")
            staff_page.get_by_role("button", name="Confirm claim").click()
            assert (
                "confirm with your pin"
                in staff_page.locator("h2").inner_text().casefold()
            )
            capture(staff_page, "pin")
            staff_page.get_by_label("Staff PIN").fill("9999")
            staff_page.get_by_role("button", name="Confirm action").click()
            assert staff_page.locator(".error").count() == 1
            staff_page.get_by_label("Staff PIN").fill("1234")
            staff_page.get_by_role("button", name="Confirm action").click()
            staff_page.wait_for_url(re.compile(r".*/jobs/\d+/"))
            assert "Claimed" in staff_page.locator("article").inner_text()
            staff_page.goto(base + f"/jobs/{number}/history/")
            assert "TEST browser staff" in staff_page.locator(".tl").inner_text()
            code, url = create_device("TEST browser personal", "personal")
            personal_ctx = context()
            personal_page = personal_ctx.new_page()
            personal_page.goto(url)
            personal_page.get_by_role("link", name="Continue to setup").click()
            personal_page.get_by_label("Six-digit setup code").fill(code)
            personal_page.get_by_role(
                "button", name="Set up this device", exact=True
            ).click()
            personal_page.wait_for_url("**/shift/")
            capture(personal_page, "shift")
            from concurrent.futures import ThreadPoolExecutor

            def full_mode():
                from django.db import close_old_connections

                try:
                    with shop_context(shop):
                        branch = Branch.objects.get(code="DEMO")
                        branch.simple_mode = False
                        branch.save(update_fields=["simple_mode"])
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(full_mode).result()
            personal_page.get_by_label("Staff name").select_option(
                label="TEST browser staff"
            )
            personal_page.get_by_label("Four-digit PIN").fill("1234")
            personal_page.get_by_role("button", name="Start shift").click()
            personal_page.wait_for_url("**/jobs/")
            assert (
                "TEST browser staff" in personal_page.locator(".identity").inner_text()
            )
            personal_page.goto(base + "/jobs/new/")
            personal_page.get_by_label("DEMO Wash-dry-fold").check()
            personal_page.get_by_label("Clothes weight (kg)").fill("1")
            personal_page.get_by_label("Cash at drop-off", exact=True).check()
            personal_page.get_by_role("button", name="Create job & show stub").click()
            personal_page.wait_for_url(re.compile(r".*/jobs/\d+/"))
            assert "TEST browser staff" in personal_page.locator("article").inner_text()
            capture(personal_page, "personal-stub")
            personal_page.get_by_role("button", name="End shift").click()
            personal_page.wait_for_url("**/shift/")
            assert any(c["name"] == "washday_device" for c in personal_ctx.cookies())
            state = personal_ctx.storage_state()
            personal_ctx.close()
            reopened = context()
            reopened.add_cookies(state["cookies"])
            page = reopened.new_page()
            page.goto(
                base
                + "/device/setup/?invite="
                + parse_qs(urlsplit(url).query)["invite"][0]
            )
            page.wait_for_url("**/shift/")
            owner_page.goto(base + "/owner/")
            tile = owner_page.locator(
                "section",
                has=owner_page.get_by_role(
                    "heading", name="TEST browser counter", exact=True
                ),
            )
            tile.get_by_role("button", name="Revoke device").click()
            staff_page.goto(base + "/jobs/")
            staff_page.wait_for_url("**/device/setup/")
            assert not external and not errors, (external, errors)
            (OUT / "browser.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "widths": [360, 390, 1280],
                        "themes": ["light", "dark"],
                        "flows": [
                            "owner fixture session and scoped provisioning",
                            "QR SVG and install without enrolment",
                            "code enrolment and cookie flags",
                            "shared unpaid intake device actor",
                            "shared claim PIN and staff actor",
                            "wrong PIN no mutation",
                            "personal shift and full-mode Jobs landing",
                            "personal payment without another PIN",
                            "end shift and reopen preserves enrolment",
                            "owner revocation blocks next request",
                        ],
                        "oauth": "Real allauth callback covered by tests with mocked Google exchange; real Google consent requires user local env credentials. No Google request in this probe.",
                        "external_requests": external,
                        "javascript_errors": errors,
                    },
                    indent=2,
                )
                + "\n"
            )
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        serverlog.close()
print(
    "Authentication browser PASS; no real Google credentials or external requests used."
)
