"""Selbst gemalte Texturen (Holz) fuer das Spielbrett-Design. Nur Pillow, keine fremden Grafiken."""
import random

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    PIL_OK = True
except ImportError:
    PIL_OK = False


def wood(w, h, base=(128, 82, 46), seed=11):
    """Dunkles Holz mit waagerechter Maserung, feinen Rissen und Bretterfugen. Gibt ein PIL-Bild (RGB) zurueck."""
    w, h = max(8, int(w)), max(8, int(h))
    rnd = random.Random(seed)
    dark = tuple(int(c * 0.62) for c in base)
    light = tuple(min(255, int(c * 1.22)) for c in base)
    noise = Image.effect_noise((max(2, w // 36), h), 90)                           # in x gestreckt = Maserung
    grain = noise.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.9))
    img = ImageOps.colorize(grain, black=dark, white=light)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(max(12, h // 7)):                                                # feine dunkle Fasern
        y = rnd.randint(0, h - 1)
        x0 = rnd.randint(-40, w - 1)
        d.line([(x0, y), (x0 + rnd.randint(60, 320), y + rnd.randint(-1, 1))], fill=(40, 24, 12, rnd.randint(30, 80)), width=1)
    seam = max(160, w // 5)
    for x in range(seam, w, seam):                                                  # Bretterfugen
        d.line([(x, 0), (x, h)], fill=(30, 18, 8, 150), width=2)
        d.line([(x + 2, 0), (x + 2, h)], fill=(160, 110, 60, 40), width=1)
    d.rectangle([0, 0, w - 1, h - 1], outline=(30, 18, 8, 220), width=2)
    return img
