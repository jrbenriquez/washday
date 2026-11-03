import os, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = (
    ROOT
    / ".agents/work/washday-mvp-history/evidence"
    / os.environ.get("EVIDENCE_RUN", "verify-1")
)
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    ctx = b.new_context()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8000/jobs/new/")
    page.get_by_label("DEMO Wash-dry-fold").check()
    page.get_by_label("Clothes weight (kg)").fill("3.2")
    page.get_by_label("New customer name").fill("DEMO history browser")
    page.get_by_label("Notes / price difference explanation").fill("HISTORY-BROWSER")
    page.get_by_label("GCash at drop-off").check()
    page.get_by_label("GCash reference (optional)").fill("HISTORY-REF")
    page.get_by_role("button", name="Create job & show stub").click()
    page.wait_for_url(re.compile(r".*/jobs/\d+/"))
    number = int(page.url.rstrip("/").split("/")[-1])
    for view in ["list", "history"]:
        for width in [360, 390, 1280]:
            page.set_viewport_size({"width": width, "height": 900})
            for theme in ["light", "dark"]:
                ctx.add_cookies(
                    [
                        {
                            "name": "app_theme",
                            "value": theme,
                            "url": "http://127.0.0.1:8000",
                        }
                    ]
                )
                page.goto("http://127.0.0.1:8000/jobs/?view=" + view)
                assert not page.evaluate(
                    "document.documentElement.scrollWidth>innerWidth"
                ), (view, width, theme)
                assert (
                    page.locator(".rail [aria-current=page]")
                    .inner_text()
                    .endswith("Jobs")
                )
                page.screenshot(
                    path=str(OUT / f"{view}-{width}-{theme}.png"), full_page=True
                )
    page.goto("http://127.0.0.1:8000/jobs/?view=list&date=2000-01-01&q=HISTORY-BROWSER")
    assert "all dates" in page.locator(".screen-head").inner_text()
    assert page.get_by_role("link", name=re.compile("#" + str(number))).count() == 1
    page.locator(
        ".jrow", has_text="HISTORY-BROWSER"
    ).count()  # notes are searchable; not shown in row
    page.locator(f'.jrow[href="/jobs/{number}/history/"]').click()
    assert (
        "at drop-off" in page.locator(".tl").inner_text()
        and "HISTORY-REF" in page.locator(".tl").inner_text()
    )
    for width in [360, 390, 1280]:
        page.set_viewport_size({"width": width, "height": 900})
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
        page.screenshot(path=str(OUT / f"timeline-{width}.png"), full_page=True)
    assert page.get_by_role("link", name="Claim stub", exact=True).count() == 1
    page.goto("http://127.0.0.1:8000/jobs/?view=list&q=DOES-NOT-EXIST-XYZ")
    assert "No jobs match" in page.locator(".jlist").inner_text()
    assert not errors, errors
    (OUT / "browser.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "views": ["list", "history", "timeline"],
                "widths": [360, 390, 1280],
                "themes": ["light", "dark"],
                "flows": [
                    "all-dates notes search",
                    "event payment reference and dropoff context",
                    "timeline/stub links",
                    "empty state",
                ],
                "overflow": False,
                "errors": errors,
            },
            indent=2,
        )
        + "\n"
    )
    b.close()
print("History browser PASS")
