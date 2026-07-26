"""Generate a neutral brand glyph for HA-Forgejo.

Deliberately NOT the Forgejo logo: that is the project's trademark and this is
an unaffiliated integration. A generic git-branch mark says what the thing does
without borrowing anyone's identity.
"""

from pathlib import Path

from PIL import Image, ImageDraw

BG = (32, 36, 46, 255)
FG = (124, 196, 168, 255)


def draw(size: int) -> Image.Image:
    s = size * 4  # supersample, then downscale for smooth edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=BG)

    r = int(s * 0.075)          # node radius
    lw = int(s * 0.055)         # line width
    left_x, right_x = int(s * 0.34), int(s * 0.66)
    top_y, mid_y, bot_y = int(s * 0.26), int(s * 0.5), int(s * 0.74)

    # trunk
    d.line([(left_x, top_y), (left_x, bot_y)], fill=FG, width=lw)
    # branch out and up
    d.line([(left_x, mid_y), (right_x, mid_y)], fill=FG, width=lw)
    d.line([(right_x, mid_y), (right_x, top_y)], fill=FG, width=lw)

    # Round off the elbow; square line caps leave a visible nub at the corner.
    d.ellipse(
        [right_x - lw // 2, mid_y - lw // 2, right_x + lw // 2, mid_y + lw // 2],
        fill=FG,
    )

    for cx, cy in ((left_x, top_y), (left_x, bot_y), (right_x, top_y)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FG)

    return img.resize((size, size), Image.LANCZOS)


OUT = Path(__file__).resolve().parent.parent / "custom_components/forgejo/brand"

for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
    draw(size).save(OUT / name)
print(f"written to {OUT}")
