"""Render site/og-image.png (1200x630) with current database stats.

Called from build_site.py; regenerated on every build so link previews on
social platforms always show fresh numbers.
"""

from pathlib import Path

from config import SITE_DIR

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


CARD_SPEC = "v2|Flock Crime Prevention Tracker|A daily-updated database of news stories in which Flock Safety cameras helped solve or prevent a crime.|flockstopscrime.com|blue-gradient"


def make_og_image() -> None:
    """Static branded card — no counts or dates, so cached social previews
    can never go stale or contradict the live site."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow unavailable; skipping og-image")
        return

    W, H = 1200, 630
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    c1, c2 = (28, 92, 171), (42, 120, 214)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))

    white = (255, 255, 255)
    draw.text((70, 130), "Flock Crime", font=_font(96), fill=white)
    draw.text((70, 235), "Prevention Tracker", font=_font(96), fill=white)
    draw.text((70, 380), "A daily-updated database of news stories in which",
              font=_font(34, bold=False), fill=(225, 235, 250))
    draw.text((70, 425), "Flock Safety cameras helped solve or prevent a crime.",
              font=_font(34, bold=False), fill=(225, 235, 250))

    draw.rectangle([(0, 540), (W, H)], fill=(16, 55, 105))
    draw.text((70, 565), "flockstopscrime.com", font=_font(34), fill=white)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    # Content-addressed filename: any change to the card changes the URL, so no
    # social-platform cache can ever serve a stale copy. Old files are removed.
    import hashlib, io
    buf = io.BytesIO(); img.save(buf, format="PNG")
    # Hash the card's CONTENT SPEC (not the pixels): pixel output varies by
    # font availability across machines, but the URL should only change when
    # the design actually changes.
    digest = hashlib.sha1(CARD_SPEC.encode()).hexdigest()[:10]
    for old in SITE_DIR.glob("og-card-*.png"):
        old.unlink()
    name = f"og-card-{digest}.png"
    (SITE_DIR / name).write_bytes(buf.getvalue())
    (SITE_DIR / "og-image.png").write_bytes(buf.getvalue())  # legacy path, still valid
    (SITE_DIR / "og-card.txt").write_text(name)
    print(f"{name} rendered (static)")


if __name__ == "__main__":
    make_og_image()
