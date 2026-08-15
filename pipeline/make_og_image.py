"""Render site/og-image.png (1200x630) with current database stats.

Called from build_site.py; regenerated on every build so link previews on
social platforms always show fresh numbers.
"""

from datetime import date
from pathlib import Path

from config import SITE_DIR
from store import load_stories

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font(size, bold=True):
    from PIL import ImageFont
    paths = FONT_PATHS if bold else FONT_PATHS[1:] + FONT_PATHS[:1]
    for p in paths:
        if ("Bold" in p) == bold and Path(p).exists():
            return ImageFont.truetype(p, size)
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_og_image() -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow unavailable; skipping og-image")
        return

    stories = load_stories()
    n = len(stories)
    states = len({r["state"] for r in stories if r.get("state")})
    years = sorted({(r.get("incident_date") or r.get("date_added") or "")[:4]
                    for r in stories if (r.get("incident_date") or r.get("date_added"))})
    span = f"{years[0]}–{years[-1]}" if years else ""

    W, H = 1200, 630
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    # diagonal-ish gradient #1c5cab -> #2a78d6
    c1, c2 = (28, 92, 171), (42, 120, 214)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))

    white = (255, 255, 255)
    draw.text((70, 90), str(n), font=_font(170), fill=white)
    label = "documented cases of Flock Safety cameras"
    label2 = "helping solve or prevent a crime"
    draw.text((70, 290), label, font=_font(44), fill=white)
    draw.text((70, 345), label2, font=_font(44), fill=white)

    sub = f"{states} states   ·   {span}   ·   updated {date.today().strftime('%B %d, %Y')}"
    draw.text((70, 440), sub, font=_font(30, bold=False), fill=(225, 235, 250))

    # footer bar
    draw.rectangle([(0, 540), (W, H)], fill=(16, 55, 105))
    draw.text((70, 565), "flockstopscrime.com", font=_font(34), fill=white)
    draw.text((640, 570), "every case independently sourced", font=_font(26, bold=False), fill=(200, 216, 240))

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(SITE_DIR / "og-image.png")
    print(f"og-image.png rendered ({n} cases)")


if __name__ == "__main__":
    make_og_image()
