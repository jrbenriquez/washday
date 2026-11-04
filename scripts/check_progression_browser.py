import re, json, os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".agents/work/washday-mvp-progression/evidence"
OUT = OUT / os.environ.get("EVIDENCE_RUN", "latest")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("CHROMIUM_PATH"), args=["--no-sandbox"]
    )
    ctx = browser.new_context()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8000/jobs/new/")
    page.get_by_label("DEMO Wash-dry-fold").check()
    page.get_by_label("Clothes weight (kg)").fill("2")
    page.get_by_label("New customer name").fill("DEMO progression browser")
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    number = int(page.url.rstrip("/").split("/")[-1])
    page.goto("http://127.0.0.1:8000/jobs/")
    card = page.locator(f'[data-job="{number}"]')
    assert "Received" in card.locator("xpath=..").locator("h3").inner_text()
    card.get_by_role("button", name=f"Move job {number} to Ready").click()
    page.wait_for_url("**/jobs/")
    assert (
        "Ready"
        in page.locator(f'[data-job="{number}"]')
        .locator("xpath=..")
        .locator("h3")
        .inner_text()
    )
    assert page.locator("#board").get_attribute("hx-trigger") == "every 20s"
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            ctx.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.reload()
            assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
            page.screenshot(
                path=str(OUT / f"board-{width}-{theme}.png"), full_page=True
            )
    page.locator(f'[data-job="{number}"]').get_by_role(
        "link", name="Correct stage"
    ).click()
    page.get_by_role("radio", name="Received", exact=True).check()
    page.get_by_label("Reason (optional)").fill("Browser correction")
    page.get_by_role("button", name="Save stage").click()
    page.wait_for_url("**/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "button", name=f"Move job {number} to Ready"
    ).click()
    page.wait_for_url("**/jobs/")
    page.locator(f'[data-job="{number}"]').get_by_role(
        "link", name="Claim & pay", exact=True
    ).click()
    page.get_by_label("Payment method").select_option("gcash")
    page.get_by_label("GCash reference (optional)").fill("CLAIM-BROWSER")
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        page.screenshot(path=str(OUT / f"claim-{width}.png"), full_page=True)
    page.get_by_role("button", name="Confirm claim").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    assert (
        "Claimed" in page.locator("article").inner_text()
        and "CLAIM-BROWSER" in page.locator("article").inner_text()
    )
    page.goto("http://127.0.0.1:8000/jobs/")
    assert page.locator(f'[data-job="{number}"]').count() == 0
    assert not errors, errors
    (OUT / "browser.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "job": number,
                "flows": [
                    "board independent next",
                    "manual correction/backward",
                    "first Ready return",
                    "GCash claim",
                    "claimed removed",
                    "poll every20s",
                ],
                "widths": [360, 390, 1280],
                "themes": ["light", "dark"],
                "overflow": False,
                "errors": errors,
            },
            indent=2,
        )
        + "\n"
    )
    browser.close()
print("Progression browser PASS")
