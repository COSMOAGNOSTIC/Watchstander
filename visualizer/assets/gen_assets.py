"""
Generates the static texture assets for Watchstander's "Blueprint" skin --
an engineering-schematic deck plan, not a rendering of any real vessel.
Run once; committed output lives alongside this script. Re-run and
re-commit if the look needs to change - Godot just loads the PNGs, no
runtime generation.

See ARCHITECTURE.md Section 8 for why this is procedural instead of an
imported real ship CAD drawing: Godot 4 has no native 2D CAD import path,
and available "open" ship general-arrangement drawings are commercial CAD
marketplace content with unclear reuse licensing. A schematic is
license-clean and, since the deck geometry here is illustrative rather
than case-accurate, more honest than a real-looking drawing would be.
"""
from PIL import Image, ImageDraw, ImageFilter

W, H = 960, 540

BLUEPRINT_BG = (10, 22, 38)
GRID_LINE = (34, 58, 82)
GRID_LINE_MAJOR = (52, 84, 114)
DECK_LINE = (90, 140, 180)
WATER_HATCH = (24, 70, 90)


def bg_blueprint():
    img = Image.new("RGB", (W, H), BLUEPRINT_BG)
    d = ImageDraw.Draw(img)

    # Frame grid -- fine vertical lines every 8px, a heavier line every 40px
    # (a "frame tick"), consistent with WorkPackageState.spatial.frame_start/end
    # being the horizontal axis the visualizer maps work packages onto.
    for x in range(0, W, 8):
        color = GRID_LINE_MAJOR if x % 40 == 0 else GRID_LINE
        d.line([(x, 0), (x, H)], fill=color, width=1)

    # Deck-level bands -- horizontal, matching Main.gd's DECK_BANDS.
    for y in (60, 160, 260, 360, 460):
        d.line([(0, y), (W, y)], fill=DECK_LINE, width=2)

    # Waterline hatch below the lowest deck band, representing the
    # over-the-side / over-water region.
    hatch = Image.new("RGB", (W, H - 460), WATER_HATCH)
    hd = ImageDraw.Draw(hatch)
    for x in range(-H, W, 14):
        hd.line([(x, 0), (x + (H - 460), H - 460)], fill=BLUEPRINT_BG, width=2)
    img.paste(hatch, (0, 460))

    # subtle vignette, same treatment as the other two visualizer skins
    vign = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse([-200, -150, W + 200, H + 150], fill=95)
    vign = vign.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, dark, vign)
    return img


def glow_sprite(size=140, color=(255, 255, 255)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * 0.16
    cx = cy = size / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    img = img.filter(ImageFilter.GaussianBlur(size * 0.12))
    return img


def compartment_tile(size=64, color=(90, 140, 180)):
    """A translucent labeled-rectangle look for compartment cells."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, size - 2, size - 2], outline=color + (200,), width=2)
    d.rectangle([1, 1, size - 2, size - 2], fill=color + (30,))
    return img


def marker_pin(size=56, outline_width=4):
    """
    A crisp, opaque "map pin" dot -- white fill, dark outline, no blur.
    Added 2026-08-08 (ARCHITECTURE.md ADR-028) to replace `glow_sprite()`
    as `Main.gd`'s work-package/review-station marker on the real print
    backgrounds (ADR-025/ADR-027): `glow_sprite()`'s soft Gaussian-blurred
    circle was designed to read as a glow against the dark procedural
    schematic (`bg_blueprint.png`) and reads as an unreadable smudge
    against a real drawing's white/cream paper -- reported directly
    ("it looks like a colored smudge... make the pinpoints not look like
    an ink smudge"). `Main.gd` tints the white fill via `modulate` at
    runtime (hazard-category color); the dark outline is drawn UNDER the
    white fill here so it stays a constant, hazard-color-independent ring
    that keeps every marker legible against white regardless of hue.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size / 2 - outline_width - 1
    cx = cy = size / 2
    d.ellipse(
        [cx - r - outline_width, cy - r - outline_width, cx + r + outline_width, cy + r + outline_width],
        fill=(20, 22, 28, 255),
    )
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
    return img


bg_blueprint().save("bg_blueprint.png")
glow_sprite().save("node_glow.png")
compartment_tile().save("compartment_tile.png")
marker_pin().save("marker_pin.png")
print("assets written")
