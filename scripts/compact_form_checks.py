"""Interaction and stress checks for check_ui_layout.py --compact-forms.

Only called inside that runner's temporary SQLite fixture, never a live shop.
"""
import json


def verify_compact_forms(page, ctx, base, paths, out):
    results = []
    metrics = {}
    contrast = {}
    for name in ["staff", "access", "branch-editor", "settings"]:
        page.set_viewport_size({"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "app_theme", "value": "light", "url": base}])
        page.goto(base + paths[name])
        form = page.locator(".compact-form").first
        controls = form.locator('input:not([type=hidden]):not(:disabled),select:not(:disabled),button')
        controls.first.focus()
        previous = controls.first
        for control in controls.all()[1:]:
            # Native time inputs have several internal tab stops (hour/minute/AM).
            for _ in range(8):
                page.keyboard.press("Tab")
                if not previous.evaluate("e => e === document.activeElement"):
                    break
            assert control.evaluate("e => e === document.activeElement"), (name, "tab order")
            previous = control
        for theme in ["light", "dark"]:
            ctx.add_cookies([{"name": "app_theme", "value": theme, "url": base}])
            page.goto(base + paths[name])
            pairs = form.evaluate("""form => {
                const style = getComputedStyle(form), root = getComputedStyle(document.documentElement);
                const surface = getComputedStyle(form.closest('.card')).backgroundColor;
                const input = form.querySelector('input:not([type=hidden]):not([type=checkbox])');
                const button = form.querySelector('.primary');
                return {ink:[style.color,surface], muted:[root.getPropertyValue('--muted').trim(),surface],
                    boundary:[getComputedStyle(input).borderTopColor,surface],
                    focus:[root.getPropertyValue('--accent').trim(),surface],
                    primary:[getComputedStyle(button).color,getComputedStyle(button).backgroundColor]};
            }""")
            def luminance(color):
                import re
                if color.startswith('#'):
                    rgb = [int(color[i:i+2], 16) / 255 for i in [1, 3, 5]]
                else:
                    rgb = [float(v) / 255 for v in re.findall(r"[\d.]+", color)[:3]]
                linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
                return sum(v*w for v, w in zip(linear, [.2126, .7152, .0722]))
            ratios = {}
            for role, pair in pairs.items():
                light, dark = sorted([luminance(c) for c in pair], reverse=True)
                ratio = (light + .05) / (dark + .05)
                assert ratio >= (3 if role in ['boundary', 'focus'] else 4.5), (name, theme, role, ratio)
                ratios[role] = {"colors": pair, "ratio": round(ratio, 2)}
            contrast[name + '-' + theme] = ratios
        metrics[name] = form.evaluate("e => ({width:e.offsetWidth,height:e.offsetHeight})")
        for width, direction, zoom, long_labels in [
            (320, "ltr", 1, False), (1280, "rtl", 1, False),
            (1280, "ltr", 2, False), (640, "ltr", 1, False),
            (320, "rtl", 1, True),
        ]:
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(base + paths[name])
            page.evaluate("([dir,zoom]) => {document.documentElement.dir=dir; document.body.style.zoom=zoom}", [direction, zoom])
            if long_labels:
                form.locator("label").evaluate_all("els => els.forEach(e => e.append(' — Extended translated field label for layout verification'))")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (name, width, direction, zoom)
            controls = form.locator("input:not([type=hidden]),select,button")
            for control in controls.all():
                if control.is_disabled():
                    continue
                control.focus()
                assert control.evaluate("e => e === document.activeElement")
                assert control.evaluate("e => getComputedStyle(e).outlineStyle !== 'none'")
                assert control.evaluate("e => {const r=e.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth+1}")
            if zoom == 2:
                page.screenshot(path=str(out / f"{name}-css-zoom-200.png"), full_page=True)
            results.append({"page": name, "width": width, "direction": direction, "css_zoom": zoom, "long_labels": long_labels})
    page.set_viewport_size({"width": 390, "height": 900})
    ctx.add_cookies([{"name": "app_theme", "value": "dark", "url": base}])
    # Server validation preserves branch values and focuses the invalid field.
    page.goto(base + paths["branch-editor"])
    page.locator('[name="name"]').fill("")
    page.locator(".compact-form").evaluate("e => e.noValidate=true")
    with page.expect_navigation() as nav:
        page.get_by_role("button", name="Save branch", exact=True).click()
    assert nav.value.status == 422
    assert page.locator('[name="code"]').input_value() == "DEMO"
    assert page.locator('[name="name"]').evaluate("e => e === document.activeElement")
    page.screenshot(path=str(out / "branch-error-390-dark.png"), full_page=True)
    page.locator('[name="name"]').fill("DEMO branch · not operating data")
    page.get_by_role("button", name="Save branch", exact=True).click()
    assert page.url.endswith("/owner/branches/manage/")
    results.append({"interaction": "branch validation and recovery", "result": "PASS"})
    # Personal phones need an assignment; the correction keeps name/type intact.
    page.goto(base + paths["access"])
    page.locator('[name="name"]').fill("DEMO personal phone")
    page.locator('[name="kind"]').select_option("personal")
    with page.expect_navigation() as nav:
        page.get_by_role("button", name="Create setup invitation").click()
    assert nav.value.status == 422
    assert page.locator('[name="name"]').input_value() == "DEMO personal phone"
    assert page.locator('[name="assigned_staff"]').evaluate("e => e === document.activeElement")
    page.screenshot(path=str(out / "device-error-390-dark.png"), full_page=True)
    page.locator('[name="assigned_staff"]').select_option(index=1)
    page.get_by_role("button", name="Create setup invitation").click()
    assert len(page.get_by_label("Six-digit setup code").inner_text()) == 6
    results.append({"interaction": "personal phone validation, recovery and invitation", "result": "PASS"})
    # Staff PIN validation and generated-PIN success.
    page.goto(base + paths["staff"])
    form = page.locator(".compact-form")
    form.locator('[name="name"]').fill("DEMO compact staff")
    form.locator('[name="pin"]').fill("12")
    with page.expect_navigation() as nav:
        form.get_by_role("button", name="Add staff", exact=True).click()
    assert nav.value.status == 422
    assert page.locator('[name="name"]').first.input_value() == "DEMO compact staff"
    assert page.locator('[name="pin"]').first.evaluate("e => e === document.activeElement")
    page.locator(".compact-form").get_by_role("button", name="Add staff", exact=True).click()
    assert len(page.get_by_label("New staff PIN").inner_text()) == 4
    results.append({"interaction": "staff validation, recovery and generated PIN", "result": "PASS"})
    # Branding uses the original multipart form and persists the shop name.
    page.goto(base + paths["settings"])
    form = page.locator(".branding-settings form")
    form.locator('[name="name"]').fill("DEMO compact shop")
    form.get_by_role("button", name="Save shop branding").click()
    assert page.locator('.branding-settings [name="name"]').input_value() == "DEMO compact shop"
    results.append({"interaction": "branding name save", "result": "PASS"})
    (out / "form-checks.json").write_text(json.dumps({"metrics": metrics, "contrast": contrast, "checks": results, "native_zoom": "Not verified; CSS zoom and 640px reflow tested", "screen_reader": "Not verified"}, indent=2) + "\n")
