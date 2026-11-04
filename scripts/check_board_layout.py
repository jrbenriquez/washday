"""Check the live board's prototype layout. Run against a seeded demo server."""

import os
from playwright.sync_api import sync_playwright

base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    for width in (390, 1280, 1440):
        page.set_viewport_size({"width": width, "height": 1000})
        for theme in ("light", "dark"):
            page.context.add_cookies([{"name": "app_theme", "value": theme, "url": base}])
            page.goto(base + "/jobs/")
            page.evaluate("document.fonts.ready")
            assert page.locator(".rail a svg").count() == page.locator(".rail a").count()
            for icon in page.locator(".rail a svg").all():
                assert icon.evaluate("e => Math.abs((e.getBoundingClientRect().left + e.getBoundingClientRect().width/2) - (e.parentElement.getBoundingClientRect().left + e.parentElement.getBoundingClientRect().width/2)) < 1")
            assert page.locator('.jobs-views a[aria-current="page"]').inner_text() == "Board"
            cards = page.locator(".ocard")
            assert cards.count(), "Seed jobs before checking board layout"
            for card in cards.all():
                assert card.locator(".open .row").count() == 2
                assert card.locator(".open .row").first.locator(".mono").count() == 1
                assert card.locator(".card-acts svg").count() == 1
                for pill in card.locator(".pill").all():
                    assert pill.bounding_box()["width"] < card.bounding_box()["width"] * .8
                action = card.locator(".card-acts")
                assert action.bounding_box()["height"] <= 60
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser.close()
print("Board layout: 6 viewport/theme cases passed")
