"""
generar_icono.py — Ícono del Transcriptor con la paleta "Tu Tiendita IA".

Globo de diálogo con renglones de transcripción, cada uno con el punto de
color de su hablante (diarización) y un cursor Malvón de escritura.
Se dibuja a 1024 px y se reduce con Lanczos.

Genera: transcriptor.png (1024), transcriptor_256.png y transcriptor.ico.
Uso:  python generar_icono.py
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

OUT = Path(__file__).resolve().parent
S = 1024
M = 44
R = 236
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

BIROME = "#1E3C96"
TINTA = "#16205A"
MALVON = "#E0435C"
YEMA = "#FFD23F"
PAPEL = "#F6F7FA"
CELESTE = "#AFC0FF"


def hex_rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def diagonal_gradient(c1, c2):
    a, b = hex_rgb(c1), hex_rgb(c2)
    small = Image.new("RGBA", (256, 256))
    px = small.load()
    for y in range(256):
        for x in range(256):
            t = min(1.0, max(0.0, (x * 0.45 + y * 0.85) / (255 * 1.3)))
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(4))
    return small.resize((S, S), Image.Resampling.BICUBIC)


def base_tile(c1, c2, glow):
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((M, M, S - M, S - M), radius=R, fill=255)
    tile = diagonal_gradient(c1, c2)

    cx, cy, rad, color, alpha = glow
    g = Image.new("L", (S, S), 0)
    ImageDraw.Draw(g).ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=alpha)
    layer = Image.new("RGBA", (S, S), hex_rgb(color, 0))
    layer.putalpha(g.filter(ImageFilter.GaussianBlur(rad * 0.45)))
    tile = Image.alpha_composite(tile, layer)

    sheen = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(sheen)
    for y in range(M, S // 2):
        d.line((0, y, S, y), fill=int(46 * (1 - (y - M) / (S // 2 - M)) ** 1.6))
    white = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    white.putalpha(sheen)
    tile = Image.alpha_composite(tile, white)

    ring = Image.new("L", (S, S), 0)
    ImageDraw.Draw(ring).rounded_rectangle((M + 3, M + 3, S - M - 3, S - M - 3), radius=R - 3, outline=60, width=7)
    w2 = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    w2.putalpha(ring)
    tile = Image.alpha_composite(tile, w2)

    tile.putalpha(ImageChops.multiply(tile.getchannel("A"), mask))
    return tile


def with_shadow(glyph, color=(5, 8, 25), alpha=110, offset=18, blur=26):
    a = glyph.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", glyph.size, color + (0,))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", glyph.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, offset))
    return Image.alpha_composite(out, glyph)


def icono(small=False):
    tile = base_tile("#3550C8", "#5A2A86", glow=(760, 260, 320, MALVON, 110))
    g = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)

    # Globo de diálogo con cola abajo a la izquierda
    box = (176, 212, 848, 712)
    d.rounded_rectangle(box, radius=120, fill=hex_rgb(PAPEL))
    d.polygon([(262, 650), (226, 846), (430, 690)], fill=hex_rgb(PAPEL))
    d.line([(262, 650), (226, 846), (430, 690)], fill=hex_rgb(PAPEL), width=40, joint="curve")
    d.ellipse((206, 826, 246, 866), fill=hex_rgb(PAPEL))

    # Renglones: punto del hablante + texto
    if small:
        rows = [(370, BIROME, 760), (554, MALVON, 640)]
        dot, th = 52, 62
    else:
        rows = [(332, BIROME, 760), (462, MALVON, 690), (592, "#F2B807", 590)]
        dot, th = 40, 46
    for y, color, end in rows:
        d.ellipse((268 - dot, y - dot, 268 + dot, y + dot), fill=hex_rgb(color))
        d.rounded_rectangle((346, y - th / 2, end, y + th / 2), radius=th / 2, fill=hex_rgb(TINTA, 225))

    # Cursor de escritura al final del último renglón
    y_last, _, end_last = rows[-1]
    cx = end_last + (44 if small else 40)
    d.rounded_rectangle((cx - 14, y_last - 54, cx + 14, y_last + 54), radius=14, fill=hex_rgb(MALVON))

    return Image.alpha_composite(tile, with_shadow(g))


def export(name, img, small_img):
    img.save(OUT / f"{name}.png")
    img.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / f"{name}_256.png")
    frames = [(small_img if s <= 24 else img).resize((s, s), Image.Resampling.LANCZOS) for s in ICO_SIZES]
    frames[-1].save(OUT / f"{name}.ico", sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])


if __name__ == "__main__":
    grande, chico = icono(), icono(small=True)
    export("transcriptor", grande, chico)

    prev = Image.new("RGBA", (420, 400), hex_rgb("#0A1024"))
    prev.alpha_composite(Image.new("RGBA", (420, 80), hex_rgb("#E9ECF3")), (0, 320))
    prev.alpha_composite(grande.resize((220, 220), Image.Resampling.LANCZOS), (100, 16))
    cx = 100
    for s in (48, 32, 24, 16):
        src = chico if s <= 24 else grande
        prev.alpha_composite(src.resize((s, s), Image.Resampling.LANCZOS), (cx, 250 + (48 - s)))
        prev.alpha_composite(src.resize((s, s), Image.Resampling.LANCZOS), (cx, 336 + (48 - s) // 2))
        cx += s + 22
    prev.save(OUT / "vista_previa.png")
    print("Ícono generado en", OUT)
