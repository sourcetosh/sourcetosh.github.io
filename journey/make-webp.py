"""Makes the Journey's pictures from the originals in ../Portfolio images.

Each photo is cropped square about its heart, which lands on the bindu, then faded into the page:
the paper goes pure white (the page lays its own paper under it), the colour is quietened, and
the pigment thins out towards the frame ring in a soft, uneven edge, so the rings, the dots and
the words stay on top. Run it again after changing PHOTOS:

    python journey/make-webp.py

Chapter II has no photographs: its picture is grey smoke, painted here from noise.
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "Portfolio images"
OUT = 1600   # px, square
PAD = 1.1    # the page draws each picture a tenth past its frame ring (PAD in index.html)

# chapter: file; heart, as fractions of its width and height; ring, the frame ring's radius as a
# fraction of its shorter side; strength, how much pigment stays at the heart; colour, how much of
# its saturation survives; fade, where the pigment starts to thin and where it is gone (frame
# ring = 1); wide, how much further the fade reaches sideways than up and down.
DEFAULT = dict(strength=.54, colour=.6, fade=(.36, .9), wide=1)
PHOTOS = {
    1: dict(file="chidhood photo.png", heart=(.355, .47), ring=.52, strength=.56, colour=.62),  # the child in the big dress
    3: dict(file="Gold medal_Msc.png", heart=(.625, .54), ring=.42, strength=.46, colour=.5),   # the medal, handed over
    4: dict(file="CCMB lab.png", heart=(.27, .57), ring=.42),                                    # at the bench, the hands
    5: dict(file="AnubhutiHealth Early Team.png", heart=(.5, .45), ring=.9, strength=.5, colour=.55, fade=(.45, .92), wide=1.3),  # the whole row
    6: dict(file="at IIT.png", heart=(.715, .5), ring=.46),                                      # me, at IIT Patna
    7: dict(file="podcast at clinic.png", heart=(.465, .48), ring=.8, fade=(.45, .95), wide=1.35),  # the two of us, talking
    8: dict(file="into the mountains.png", heart=(.45, .62), ring=.55, strength=.56, colour=.62, fade=(.45, .95), wide=1.1),  # me, the hills above, the river below
    9: dict(file="Guru.png", heart=(.41, .45), ring=.34, strength=.74, colour=.68, fade=(.5, .95)),  # the flower, fuller than the rest
}
EDGE = .09  # where a photo's own content runs to its border, it thins to paper over this much of its short side
SMOKE = dict(k=2, strength=.5, fade=(.3, .9), seed=7)  # the metamorphosis year


def smooth(a, b, x):
    t = min(1, max(0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def value_noise(seed):
    """Smooth 2D noise, and five octaves of it (each twice as fine, turned about 37 degrees)."""
    rnd = random.Random(seed)
    perm = list(range(256))
    rnd.shuffle(perm)
    perm += perm
    vals = [rnd.random() for _ in range(256)]

    def noise(x, y):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        a, b = vals[perm[perm[xi] + yi]], vals[perm[perm[xi + 1] + yi]]
        c, d = vals[perm[perm[xi] + yi + 1]], vals[perm[perm[xi + 1] + yi + 1]]
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v

    def fbm(x, y):
        s, amp = 0, .5
        for _ in range(5):
            s += amp * noise(x, y)
            x, y = x * 1.6 - y * 1.2 + 3.1, x * 1.2 + y * 1.6 + 1.7
            amp *= .5
        return s / .96875

    return fbm


def paper_of(im):
    """The photo's own paper: the brightest of its corners, read a little way in."""
    w, h = im.size
    best = (0, 0, 0)
    for x0, y0 in ((.02, .02), (.98, .02), (.02, .98), (.98, .98)):
        box = (int(x0 * w) - 12, int(y0 * h) - 12, int(x0 * w) + 12, int(y0 * h) + 12)
        c = im.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))
        if sum(c) > sum(best):
            best = c
    return best


def edge_mask(size, seed, fade, wide):
    """1 at the heart, thinning to 0 by fade[1] of the frame ring, the edge wandering a little."""
    n = 360
    rnd = random.Random(seed)
    waves = [(k, rnd.uniform(0, math.tau), a) for k, a in ((2, .045), (3, .05), (5, .03), (8, .018), (13, .01))]
    m = Image.new("L", (n, n))
    px = m.load()
    half = n / 2
    for y in range(n):
        for x in range(n):
            dx, dy = (x + .5 - half) / half * PAD, (y + .5 - half) / half * PAD
            r = math.hypot(dx / wide, dy)
            th = math.atan2(dy, dx)
            r *= 1 + sum(a * math.sin(k * th + p) for k, p, a in waves)
            t = min(1, max(0, (r - fade[0]) / (fade[1] - fade[0])))
            v = 1 - t * t * (3 - 2 * t)
            px[x, y] = round(255 * v)
    return m.resize((size, size), Image.BICUBIC).filter(ImageFilter.GaussianBlur(size / 400))


def border_mask(w, h, seed):
    """1 inside the photo, thinning to 0 at its own borders along a wandering line."""
    k = 400 / max(w, h)
    n, m = max(2, round(w * k)), max(2, round(h * k))
    band = EDGE * min(n, m)
    rnd = random.Random(seed)
    waves = [(f, rnd.uniform(0, math.tau)) for f in (3, 7, 13)]
    wob = lambda s: sum(math.sin(f * s * math.tau + p) for f, p in waves) / 3
    out = Image.new("L", (n, m))
    px = out.load()
    for y in range(m):
        for x in range(n):
            d = min(x + (wob(y / m) + 1) * band * .25, n - 1 - x + (wob(y / m + .5) + 1) * band * .25,
                    y + (wob(x / n + .25) + 1) * band * .25, m - 1 - y + (wob(x / n + .75) + 1) * band * .25)
            t = min(1, max(0, d / band))
            px[x, y] = round(255 * t * t * (3 - 2 * t))
    return out.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(max(w, h) / 500))


def make(k, file, heart, ring, strength, colour, fade, wide):
    with Image.open(SRC / file) as im:
        im = im.convert("RGB")
    w, h = im.size
    paper = paper_of(im)
    # The paper goes white, and its grain with it; so do the photo's own borders.
    lut = []
    for c in range(3):
        lut += [min(255, round(v * 255 / paper[c] / .965)) for v in range(256)]
    im = Image.composite(im.point(lut), Image.new("RGB", (w, h), (255, 255, 255)), border_mask(w, h, 900 + k))
    # A square about the heart, the frame ring `ring` of the short side from it; white past the photo.
    R = ring * min(w, h)
    side = round(2 * PAD * R)
    cx, cy = heart[0] * w, heart[1] * h
    sq = Image.new("RGB", (side, side), (255, 255, 255))
    sq.paste(im, (round(side / 2 - cx), round(side / 2 - cy)))
    sq = sq.resize((OUT, OUT), Image.LANCZOS)
    # Quieter colour, a warmer cast, thinner pigment: each channel's pigment is scaled, so it
    # still reads as watercolour on paper, only paler.
    sq = ImageEnhance.Color(sq).enhance(colour)
    warm = (.9, 1.0, 1.1)  # less red pigment and more blue: a warmer, chandan-leaning cast
    lut = []
    for c in range(3):
        s = strength * warm[c]
        lut += [round(255 - (255 - v) * s) for v in range(256)]
    faded = sq.point(lut)
    white = Image.new("RGB", (OUT, OUT), (255, 255, 255))
    out = Image.composite(faded, white, edge_mask(OUT, 400 + k, fade, wide))
    dest = HERE / f"journey-{k}.webp"
    out.save(dest, "WEBP", quality=84, method=6)
    print(f"{file} -> {dest.name} ({dest.stat().st_size // 1024} KB)")


def smoke(k, strength, fade, seed):
    """Grey smoke curling up and out from the heart: noise warped through itself, stretched as it
    rises, with fine threads where it folds; cool grey where it is thin, warmer where it gathers."""
    n = 320
    fbm = value_noise(seed)
    img = Image.new("RGB", (n, n))
    px = img.load()
    cool, warm = (98, 103, 112), (126, 117, 107)
    for j in range(n):
        for i in range(n):
            x, y = (i / n - .5) * 3.2, (j / n - .5) * 2.2 + 4
            qx, qy = fbm(x, y), fbm(x + 5.2, y + 1.3)
            rx, ry = fbm(x + 3 * qx + 1.7, y + 3 * qy + 9.2), fbm(x + 3 * qx + 8.3, y + 3 * qy + 2.8)
            f = fbm(x + 3 * rx, y + 3 * ry)
            cloud = smooth(.4, .8, f)
            thread = (1 - abs(2 * f - 1)) ** 10 * smooth(.25, .6, qx)
            d = min(1, .7 * cloud + .5 * thread)
            t = smooth(.3, .75, ry)
            px[i, j] = tuple(round(255 - (255 - (cool[c] + (warm[c] - cool[c]) * t)) * d * strength) for c in range(3))
    img = img.resize((OUT, OUT), Image.BICUBIC).filter(ImageFilter.GaussianBlur(OUT / 900))
    white = Image.new("RGB", (OUT, OUT), (255, 255, 255))
    out = Image.composite(img, white, edge_mask(OUT, 400 + k, fade, 1))
    dest = HERE / f"journey-{k}.webp"
    out.save(dest, "WEBP", quality=84, method=6)
    print(f"smoke -> {dest.name} ({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    smoke(**SMOKE)
    for k, spec in PHOTOS.items():
        make(k, **{**DEFAULT, **spec})
