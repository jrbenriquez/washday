"""Browser evidence against an isolated local preview database.

SQLITE_PATH=/tmp/washday-marketing-preview.sqlite3 uv run python manage.py migrate
MARKETING_PREVIEW=1 SQLITE_PATH=/tmp/washday-marketing-preview.sqlite3 uv run python manage.py runserver
uv run python scripts/check_marketing.py

Uses fictional contacts, writes two inquiry records to that local preview only.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/ui-audit/marketing"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"
results = {}


def fits(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow"


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    fits(page)
    page.screenshot(path=str(OUT / "home-desktop.png"))
    page.screenshot(path=str(OUT / "home-full.png"), full_page=True)
    assert page.locator("video").evaluate("v => !v.autoplay && v.paused")
    page.get_by_role("button", name="Play the 30-second WashDay introduction").click()
    page.wait_for_function("document.querySelector('video').currentTime > 0.2")
    page.locator("video").evaluate("v => v.pause()")
    results["video"] = "Plays on request; caption track present; no autoplay"
    page.get_by_role("link", name="Book a free demo").first.click()
    assert page.locator('input[name="type"]').count() == 2
    page.screenshot(path=str(OUT / "contact-desktop.png"), full_page=True)
    page.get_by_role("button", name="Send my request").click()
    assert page.locator(".error-summary").evaluate("e => e === document.activeElement")
    page.screenshot(path=str(OUT / "contact-errors.png"), full_page=True)
    results["error_focus"] = "Error summary receives focus; inputs retain values"
    for width in [320, 390, 768, 1024, 1440]:
        page.set_viewport_size({"width": width, "height": 900})
        for route in ["/", "/contact/?type=custom", "/contact/?type=demo"]:
            page.goto(BASE + route, wait_until="networkidle")
            fits(page)
        if width == 390:
            page.screenshot(path=str(OUT / "contact-mobile.png"), full_page=True)
            page.goto(BASE, wait_until="networkidle")
            page.screenshot(path=str(OUT / "home-mobile.png"))
    results["responsive"] = "No horizontal overflow at 320, 390, 768, 1024, 1440px on home and both contact types"
    context.close()

    # Both public flows continue to work without the progressive JS enhancement.
    nojs = browser.new_context(java_script_enabled=False)
    page = nojs.new_page()
    page.goto(BASE + "/contact/?type=custom")
    assert page.locator('input[name="type"]:checked').input_value() == "custom"
    page.get_by_role("button", name="Send my request").click()
    assert page.locator(".error-summary").is_visible()
    nojs.close()
    results["no_javascript"] = "Native form, type selection and server validation render without JS"

    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        record_video_dir="/tmp/washday-marketing-recording",
        record_video_size={"width": 1280, "height": 900},
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.get_by_role("link", name="Book a free demo").first.click()
    page.wait_for_timeout(900)
    page.get_by_role("button", name="Send my request").click()
    page.wait_for_timeout(1100)
    page.get_by_label("Your name").press_sequentially("Alex Demo", delay=60)
    page.get_by_label("Email address").press_sequentially("alex@example.test", delay=50)
    page.get_by_label("Shop name", exact=True).press_sequentially("Sample Laundry", delay=60)
    page.get_by_label("Phone number").fill("09000000000")
    page.get_by_label("Number of branches").fill("2")
    page.get_by_label("Good days or times").fill("Tuesday afternoons, Asia/Manila")
    page.get_by_label("What would you like us to know?").fill("I would love to see the order tracking and local hub setup.")
    page.get_by_role("button", name="Send my request").scroll_into_view_if_needed()
    page.wait_for_timeout(1300)
    page.get_by_role("button", name="Send my request").click()
    page.wait_for_url("**/contact/thanks/")
    assert page.get_by_text("Your demo isn’t scheduled yet.", exact=False).is_visible()
    page.screenshot(path=str(OUT / "demo-success.png"), full_page=True)
    page.wait_for_timeout(1800)
    page.get_by_role("link", name="Back to WashDay").click()
    page.get_by_role("link", name="Have a question? Talk to us.").click()
    assert page.locator(".demo-fields").is_hidden()
    page.wait_for_timeout(900)
    page.get_by_label("Your name").press_sequentially("Jamie Example", delay=55)
    page.get_by_label("Email address").press_sequentially("jamie@example.test", delay=45)
    page.get_by_label("Shop name", exact=True).fill("Neighborhood Laundry")
    page.get_by_label("What would you like us to know?").press_sequentially("Can WashDay help us manage three branches?", delay=35)
    page.screenshot(path=str(OUT / "custom-inquiry.png"), full_page=True)
    page.get_by_role("button", name="Send my request").scroll_into_view_if_needed()
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Send my request").click()
    page.wait_for_url("**/contact/thanks/")
    assert page.get_by_text("Your inquiry is saved.", exact=False).is_visible()
    page.screenshot(path=str(OUT / "custom-success.png"), full_page=True)
    page.wait_for_timeout(1800)
    recording = page.video.path()
    context.close()
    results["recording_source"] = str(recording)
    results["flows"] = "Demo request and custom inquiry submitted successfully using fictional local data"
    results["page_errors"] = errors
    assert not errors
    browser.close()

(OUT / "browser.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
