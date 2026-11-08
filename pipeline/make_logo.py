"""Build the PenJaroFind lockup: icon from the supplied artwork, wordmark typeset,
everything in Sky + Umber. Kerning is corrected by measuring ink gaps, not by eye."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC = '/Users/PetroulaKostofska/.hermes/cache/documents/native-inputs/2a47fae2375062d84b1b4ca5e3e03765ce96f18e227e7cc1ad3aac056a0ecf8c/dashboard_20261101_160619_db4c01b4_image_8fb5bf.png'
UMBER, SKY, GRID = (0x71, 0x50, 0x2F), (0xA7, 0xD4, 0xE4), (0x8C, 0xBD, 0xD2)
W, H = 1024, 1008
FONT_PATH = "/System/Library/Fonts/Avenir Next.ttc"
FONT_INDEX = 5          # Medium — matches the icon's stroke weight
TEXT = "PenJaroFind"


def base_canvas():
    src = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32) / 255
    mx, mn = src.max(2), src.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    cover = np.clip((sat - 0.12) / (0.60 - 0.12), 0, 1)
    cover[725:, :] = 0                                   # keep the icon, drop the old wordmark

    bg = Image.new('RGB', (W, H), SKY)
    d = ImageDraw.Draw(bg)
    for x in range(0, W, 73):
        d.line([(x, 0), (x, H)], fill=GRID, width=2)
    for y in range(63, H, 73):
        d.line([(0, y), (W, y)], fill=GRID, width=2)
    bg = bg.filter(ImageFilter.GaussianBlur(0.6))

    canvas = np.asarray(bg).astype(np.float32) / 255
    return canvas * (1 - cover[..., None]) + (np.array(UMBER, np.float32) / 255) * cover[..., None], cover


def wordmark(track, deltas, target=780, size=700):
    font = ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)
    canvas = Image.new('L', (size * len(TEXT), size * 2), 0)
    dd = ImageDraw.Draw(canvas)
    x, baseline = size // 2, int(size * 1.15)
    for i, ch in enumerate(TEXT):
        dd.text((x, baseline), ch, font=font, fill=255, anchor="ls")
        nxt = TEXT[i + 1] if i + 1 < len(TEXT) else ""
        x += dd.textlength(ch, font=font) + (track + deltas.get((ch, nxt), 0.0)) * size
    canvas = canvas.crop(canvas.getbbox())
    return canvas.resize((target, int(canvas.height * target / canvas.width)), Image.Resampling.LANCZOS)


def measure_gaps(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
    band = a[735:855, :, :]
    ink = (band.sum(2) < 420).sum(0)                      # umber is far darker than sky or grid
    cols = np.where(ink > 0)[0]
    groups = []
    for c in cols:
        if groups and c - groups[-1][-1] <= 1:
            groups[-1].append(c)
        else:
            groups.append([c])
    return [int(groups[i + 1][0] - groups[i][-1] - 1) for i in range(len(groups) - 1)]


def build(track, deltas, out='assets/logo-penjarofind-umber-sky.png',
          trans='assets/logo-penjarofind-umber-transparent.png'):
    canvas, cover = base_canvas()
    m = wordmark(track, deltas)
    arr = np.asarray(m).astype(np.float32) / 255
    tw, th = m.size
    ox, oy = (W - tw) // 2, 744
    col = np.array(UMBER, np.float32) / 255
    region = canvas[oy:oy + th, ox:ox + tw]
    canvas[oy:oy + th, ox:ox + tw] = region * (1 - arr[..., None]) + col * arr[..., None]
    Image.fromarray((np.clip(canvas, 0, 1) * 255).round().astype(np.uint8)).save(out)

    alpha = np.zeros((H, W), np.float32)
    alpha[:725, :] = cover[:725, :]
    alpha[oy:oy + th, ox:ox + tw] = np.maximum(alpha[oy:oy + th, ox:ox + tw], arr)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0:3] = UMBER
    rgba[..., 3] = (np.clip(alpha, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(rgba, 'RGBA').save(trans)
    return out


if __name__ == "__main__":
    track = float(sys.argv[1]) if len(sys.argv) > 1 else 0.045
    pairs = sys.argv[2] if len(sys.argv) > 2 else ""
    deltas = {("n", "J"): 0.045, ("o", "F"): -0.020, ("F", "i"): 0.020, ("i", "n"): 0.005}
    for item in filter(None, pairs.split(",")):
        k, v = item.split("=")          # e.g. oF=0.02 for the o→F pair
        deltas[(k[0], k[1])] = float(v)
    out = build(track, deltas)
    gaps = measure_gaps(out)
    print("gaps:", gaps, "| mean %.1f spread %d" % (np.mean(gaps), max(gaps) - min(gaps)))
