"""Draw PERCH's icon -- the bird on its branch from the panel's titlebar mark --
as a multi-size .ico for the executable, the installer and the Start menu.

    python packaging/make_icon.py

Drawn with Pillow at 1024 px and downsampled, rather than shipped as a binary,
so the icon is reproducible from the repository like everything else.
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024 / 32                          # the mark is drawn on a 32-unit grid

# The titlebar mark's bird (ui/web/index.html, .mark-bird), as a polygon.
BIRD = [(8.2, 23.6), (4.6, 20.4), (9.7, 21.0), (10.4, 18.2), (12.0, 15.6), (14.6, 13.7),
        (17.2, 12.8), (19.5, 12.6), (21.8, 13.0), (24.4, 14.3), (27.6, 13.9), (25.5, 16.5),
        (25.9, 18.6), (25.4, 20.7), (23.9, 22.4), (21.7, 23.4), (19.3, 23.6)]
EYE = (22.4, 16.9, 1.15)


def draw() -> Image.Image:
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((32, 32, 992, 992), radius=220, fill=(20, 20, 23, 255))
    d.line([(5.2 * S, 26 * S), (26.8 * S, 26 * S)], fill=(111, 109, 104, 255), width=int(1.9 * S))
    d.polygon([(x * S, y * S) for x, y in BIRD], fill=(94, 200, 192, 255))
    x, y, r = EYE
    d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(20, 20, 23, 255))
    return img


if __name__ == "__main__":
    big = draw()
    big.resize((256, 256), Image.LANCZOS).save(
        HERE / "perch.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.resize((512, 512), Image.LANCZOS).save(HERE / "perch.png")
    print(f"wrote {HERE / 'perch.ico'} and perch.png")
