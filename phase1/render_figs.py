"""Render each <figure> in figures.html to its own PNG (chart+legend only; figcaption goes to LaTeX \\caption)."""
import pathlib
from playwright.sync_api import sync_playwright

SRC = pathlib.Path("figures.html").resolve()
FIGS = [("fig-h1", "fig1"), ("fig-regret", "fig2"), ("fig-rescue", "fig3"),
        ("fig-lowdim", "fig4"), ("fig-steer", "fig5"), ("fig-backbone", "fig6")]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 700}, device_scale_factor=2, color_scheme="light")
    pg.goto(SRC.as_uri())
    pg.wait_for_timeout(700)
    pg.add_style_tag(content="figcaption{display:none!important} "
                             ".fig{border:none!important;background:transparent!important;"
                             "padding:6px 4px!important;margin:0!important;box-shadow:none!important}")
    pg.wait_for_timeout(200)
    for fid, out in FIGS:
        el = pg.query_selector(f"#{fid}")
        el.screenshot(path=f"{out}.png")
        print("rendered", out + ".png")
    b.close()
