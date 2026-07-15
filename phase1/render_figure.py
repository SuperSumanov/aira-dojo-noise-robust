import pathlib, sys
from playwright.sync_api import sync_playwright

src = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 1400}, device_scale_factor=2,
                    color_scheme="light")
    pg.goto(src.as_uri())
    pg.wait_for_timeout(700)
    el = pg.query_selector(".wrap")
    el.screenshot(path=str(out))
    b.close()
print("rendered", out)
