"""Independent browser acceptance probe. Requires the local DEMO server on :8000."""

import json, re, os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".agents/work/washday-mvp-intake/evidence"
OUT = OUT / os.environ.get("EVIDENCE_RUN", "latest")
OUT.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/chromium", args=["--no-sandbox"]
    )
    context = browser.new_context()
    page = context.new_page()
    errors = []
    external = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def route(r):
        if r.request.url.startswith("http://127.0.0.1:8000/"):
            r.continue_()
        else:
            external.append(r.request.url)
            r.abort()

    context.route("**/*", route)
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            context.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.goto("http://127.0.0.1:8000/jobs/new/")
            page.evaluate("document.fonts.ready")
            assert page.locator("html").get_attribute("data-app-theme") == theme
            overflow = page.evaluate(
                "document.documentElement.scrollWidth > window.innerWidth"
            )
            assert not overflow, (width, theme)
            assert page.locator(".rail").evaluate(
                "(e)=>getComputedStyle(e).position"
            ) == ("fixed" if width < 760 else "static")
            assert page.locator("[data-create]").bounding_box()["height"] >= 56
            sizes = page.locator("button,a.btn,label.chip").evaluate_all(
                "(els)=>els.filter(e=>e.getBoundingClientRect().height<44).map(e=>e.outerHTML)"
            )
            assert not sizes, sizes
            fonts = page.evaluate(
                "['Figtree','Saira Condensed','JetBrains Mono'].map(f=>({font:f,loaded:document.fonts.check('600 16px \\\"'+f+'\\\"')}))"
            )
            assert all(f["loaded"] for f in fonts), fonts
            page.screenshot(
                path=str(OUT / f"intake-{width}-{theme}.png"), full_page=True
            )
            results.append(
                {
                    "view": "intake",
                    "width": width,
                    "theme": theme,
                    "overflow": False,
                    "targets": "PASS",
                    "fonts": fonts,
                }
            )
    page.set_viewport_size({"width": 390, "height": 900})
    page.get_by_label("DEMO Wash-dry-fold").check()
    page.get_by_label("Clothes weight (kg)").fill("3.1")
    page.wait_for_function(
        "document.querySelector('#summary').textContent.includes('108.50')"
    )
    page.get_by_label("GCash at drop-off").check()
    page.get_by_label("GCash reference (optional)").fill("BROWSER-REFERENCE")
    page.get_by_label("New customer name").fill("DEMO browser customer")
    page.get_by_label("Phone", exact=True).fill("0900-TEST")
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    text = page.locator("article").inner_text()
    assert (
        "108.50" in text
        and "BROWSER-REFERENCE" in text
        and "DEMO browser customer" in text
    )
    regular = page.url
    page.reload()
    assert page.locator("article").inner_text() == text
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            context.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.reload()
            assert not page.evaluate(
                "document.documentElement.scrollWidth > window.innerWidth"
            )
            page.screenshot(path=str(OUT / f"stub-{width}-{theme}.png"), full_page=True)
    page.evaluate("window.print=()=>{window.__printed=true}")
    page.get_by_role("button", name="Print stub").click()
    assert page.evaluate("window.__printed")
    page.emulate_media(media="print")
    assert (
        not page.locator(".top").is_visible() and not page.locator(".rail").is_visible()
    )
    page.pdf(
        path=str(OUT / "stub-print.pdf"),
        width="80mm",
        height="220mm",
        print_background=True,
    )
    page.emulate_media(media="screen")
    page.goto("http://127.0.0.1:8000/jobs/new/")
    page.get_by_label("Find by name or phone").fill("0900-TEST")
    page.wait_for_function(
        "document.querySelector('#customers').textContent.includes('DEMO browser customer')"
    )
    page.locator("#customers input").first.check()
    page.get_by_role("button", name="Add DEMO Comforter Queen").click()
    page.wait_for_function(
        "document.querySelector('#summary').textContent.includes('180.00')"
    )
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    assert (
        "Pieces only" in page.locator("article").inner_text()
        and "DEMO browser customer" in page.locator("article").inner_text()
    )
    page.goto("http://127.0.0.1:8000/jobs/new/?paper=1")
    sheet = (
        (datetime.now(ZoneInfo("Asia/Manila")) - timedelta(days=1)).date().isoformat()
    )
    pref = "P-" + str(int(datetime.now().timestamp()))

    def fill_paper():
        page.get_by_label("P number", exact=True).fill(pref)
        page.get_by_label("Sheet date").fill(sheet)
        page.get_by_label("Time received").fill("08:00")
        page.get_by_label("Written total (₱)").fill("100.00")
        page.get_by_label("DEMO Heavy items").check()
        page.get_by_label("Clothes weight (kg)").fill("2.0")
        page.get_by_label("Cash at drop-off", exact=True).check()
        page.get_by_label("Time paid on sheet (required if paid)").fill("08:05")

    fill_paper()
    page.wait_for_function(
        "document.querySelector('#summary').textContent.includes('270.00') && document.querySelector('#summary').textContent.includes('100.00')"
    )
    page.screenshot(path=str(OUT / "paper-1280.png"), full_page=True)
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    paper_url = page.url
    assert "Received on paper as " + pref in page.locator("article").inner_text()
    page.goto("http://127.0.0.1:8000/jobs/new/?paper=1")
    fill_paper()
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(paper_url)
    assert "already entered" in page.locator(".toast").inner_text()
    page.goto("http://127.0.0.1:8000/jobs/new/")
    old = page.locator("html").get_attribute("data-app-theme")
    page.get_by_role("button", name=re.compile("Switch to .* theme")).click()
    assert page.locator("html").get_attribute("data-app-theme") != old
    page.reload()
    assert page.locator("html").get_attribute("data-app-theme") != old
    # Visible keyboard focus is defined and actually active.
    page.get_by_label("Clothes weight (kg)").focus()
    assert (
        page.locator("#kg").evaluate("(e)=>getComputedStyle(e).outlineStyle") != "none"
    )
    assert not external, external
    assert not errors, errors
    results.append(
        {
            "flows": [
                "server summary",
                "GCash intake",
                "reload persistence",
                "customer create/search/select",
                "pieces-only",
                "paper price mismatch/provenance",
                "duplicate opens same stub",
                "cookie theme",
                "print callback and print stylesheet",
                "keyboard focus",
            ],
            "external_requests": external,
            "javascript_errors": errors,
            "regular_stub": regular,
            "paper_stub": paper_url,
            "status": "PASS",
        }
    )
    browser.close()
(OUT / "browser.json").write_text(json.dumps(results, indent=2) + "\n")
print(
    json.dumps(
        {
            "status": "PASS",
            "screen_cases": len(results) - 1,
            "evidence": str(OUT / "browser.json"),
        }
    )
)
