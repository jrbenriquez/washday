import os, re, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = (
    ROOT
    / ".agents/work/washday-mvp-machines/evidence"
    / os.environ.get("EVIDENCE_RUN", "verify-1")
)
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    ctx = b.new_context()
    page = ctx.new_page()
    errors = []
    external = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    ctx.route(
        "**/*",
        lambda r: (
            r.continue_()
            if r.request.url.startswith("http://127.0.0.1:8000/")
            else (external.append(r.request.url), r.abort())
        ),
    )
    page.goto("http://127.0.0.1:8000/jobs/new/")
    page.get_by_label("DEMO Wash-dry-fold").check()
    page.get_by_label("Clothes weight (kg)").fill("3")
    page.get_by_label("New customer name").fill("DEMO machine browser")
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    number = int(page.url.rstrip("/").split("/")[-1])
    page.goto("http://127.0.0.1:8000/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "button", name="Next · Washing"
    ).click()
    page.wait_for_url("**/machine/**")
    assert page.get_by_role("button", name="Start D1", exact=True).count() == 0
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            ctx.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.reload()
            assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
            page.screenshot(
                path=str(OUT / f"picker-{width}-{theme}.png"), full_page=True
            )
    page.get_by_role("button", name="Start W1", exact=True).click()
    page.wait_for_url("**/jobs/")
    page.goto("http://127.0.0.1:8000/machines/")
    assert page.get_by_role("button", name="Unload W1").count() == 1
    assert page.locator("[name=job],[name=job_id]").count() == 0
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            ctx.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.reload()
            assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
            page.screenshot(
                path=str(OUT / f"machines-{width}-{theme}.png"), full_page=True
            )
    page.get_by_role("button", name="Unload W1").click()
    page.wait_for_url("**/machines/")
    assert "Unloaded after" in page.locator("#machine-grid").inner_text()
    page.goto("http://127.0.0.1:8000/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "button", name="Next · Drying"
    ).click()
    page.wait_for_url("**/machine/**")
    page.get_by_role("button", name="Start D1", exact=True).click()
    page.wait_for_url("**/jobs/")
    page.goto("http://127.0.0.1:8000/machines/")
    page.get_by_role("button", name="Unload D1").click()
    page.wait_for_url("**/machines/")
    page.goto("http://127.0.0.1:8000/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "button", name="Next · Ready"
    ).click()
    page.wait_for_url("**/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "link", name="Claim", exact=True
    ).click()
    page.get_by_label("Payment method").select_option("cash")
    page.get_by_role("button", name="Confirm claim").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    assert "Claimed" in page.locator("article").inner_text()
    page.goto(f"http://127.0.0.1:8000/jobs/{number}/history/")
    text = page.locator(".tl").inner_text()
    assert (
        "Loaded W1" in text
        and "Loaded D1" in text
        and "Unloaded after" in text
        and "Released" in text
    )
    page.goto("http://127.0.0.1:8000/machines/")
    page.locator(
        ".machine-cell", has=page.get_by_role("heading", name="Washer · W1")
    ).get_by_role("link", name="Paid self-service").click()
    page.get_by_label("Payment method").select_option("gcash")
    page.get_by_role("button", name="Pay & start self-service").click()
    page.wait_for_url("**/machines/")
    assert "Self-service" in page.locator("#machine-grid").inner_text()
    page.get_by_role("button", name="Unload W1").click()
    assert not errors and not external, (errors, external)
    (OUT / "browser.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "amendment": "D-06 job starts only on board; grid monitoring/unload and jobless paid selfservice",
                "lifecycle_job": number,
                "widths": [360, 390, 1280],
                "themes": ["light", "dark"],
                "external": external,
                "errors": errors,
                "overflow": False,
                "runner": "Playwright Chromium; does not certify required Cypress execution",
            },
            indent=2,
        )
        + "\n"
    )
    b.close()
print("Machines Playwright browser PASS; Cypress separately required")
