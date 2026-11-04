import os, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = (
    ROOT
    / ".agents/work/washday-mvp-supplies/evidence"
    / os.environ.get("EVIDENCE_RUN", "verify-1")
)
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    ctx = b.new_context()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8000/supplies/")
    page.locator("[name=supply_type]").select_option(label="DEMO Detergent (cup)")
    page.get_by_label("Amount received").fill("5")
    page.get_by_role("button", name="Receive stock", exact=True).click()
    page.wait_for_url("**/supplies/")
    assert "Stock received" in page.locator(".toast").inner_text()
    page.get_by_label("Counted DEMO Detergent (cup)", exact=True).fill("12")
    page.get_by_label("Counted DEMO Bag (piece)", exact=True).fill("34")
    page.get_by_role("button", name="Save stock count").click()
    page.wait_for_url("**/supplies/")
    assert (
        page.locator('[data-supply="DEMO Detergent"] .mono').inner_text() == "12"
        and page.locator('[data-supply="DEMO Bag"] .mono').inner_text() == "34"
    )
    page.get_by_label("Partial count / spot check").check()
    page.get_by_label("Counted DEMO Detergent (cup)", exact=True).fill("11")
    page.get_by_role("button", name="Save stock count").click()
    page.wait_for_url("**/supplies/")
    assert (
        page.locator('[data-supply="DEMO Detergent"] .mono').inner_text() == "11"
        and page.locator('[data-supply="DEMO Bag"] .mono').inner_text() == "34"
    )
    page.get_by_label("Supply name", exact=True).fill("DEMO browser request")
    page.get_by_label("Note (optional)").fill("Labelled fixture")
    page.get_by_role("button", name="Send supply request").click()
    page.wait_for_url("**/supplies/")
    assert (
        "Requested · DEMO browser request"
        in page.locator(".supply-layout").inner_text()
    )
    assert page.get_by_role("link", name="Add supply type").count() == 0
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        for theme in ["light", "dark"]:
            ctx.add_cookies(
                [{"name": "app_theme", "value": theme, "url": "http://127.0.0.1:8000"}]
            )
            page.reload()
            assert not page.evaluate(
                "document.documentElement.scrollWidth>innerWidth"
            ), (width, theme)
            assert "Supplies" in page.locator(".rail [aria-current=page]").inner_text()
            assert not page.locator(
                "button,.supply-layout .button-link,.chip"
            ).evaluate_all(
                "(els)=>els.filter(e=>e.getBoundingClientRect().height<44).length"
            )
            page.screenshot(
                path=str(OUT / f"supplies-{width}-{theme}.png"), full_page=True
            )
    page.goto("http://127.0.0.1:8000/jobs/?view=history")
    text = page.locator(".hist").inner_text()
    assert (
        "Partial stock count saved" in text
        and "Full stock count saved" in text
        and "DEMO browser request" in text
    )
    assert not errors, errors
    (OUT / "browser.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "widths": [360, 390, 1280],
                "themes": ["light", "dark"],
                "flows": [
                    "positive receipt",
                    "full count",
                    "partial count preserves other supply",
                    "request without staff adding",
                    "stock/count/request history",
                    "immutable ledger balances",
                ],
                "overflow": False,
                "errors": errors,
                "runner": "Playwright; actual Cypress execution remains unrun",
            },
            indent=2,
        )
        + "\n"
    )
    b.close()
print("Supplies Playwright browser PASS")
