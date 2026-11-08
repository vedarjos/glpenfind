"""GLPenFind logo: apricot frame, sky field, oxblood artwork, needle shortened."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = '/Users/PetroulaKostofska/.hermes/cache/documents/native-inputs/16b6032ee3e4834c72f9cf693d597053c5e3c8eb407054b8fc3ed05f90cac33d/dashboard_20261101_163205_5b5b58dc_image_e0f1bf.png'
W, H = 1024, 1008
OXBLOOD, SKY, GRID, APRICOT = '#82241F', '#A7D4E4', '#8CBDD2', '#FDC57E'
BORDER = 70

# needle axis, measured from ink runs: tip near (545, 674), collar at (585, 626)
TIP = np.array([545.0, 674.0])
DIR = np.array([40.0, -48.0]); DIR /= np.linalg.norm(DIR)
TRIM = 16.0      # how much of the needle to remove
CAP_R = 6.0      # rounded cap radius after trimming


def hex2rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def ink_mask():
    src = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32) / 255
    mx, mn = src.max(2), src.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    return np.clip((sat - 0.12) / (0.60 - 0.12), 0, 1)


def shorten_needle(cover):
    yy, xx = np.mgrid[0:H, 0:W]
    rel = np.stack([xx - TIP[0], yy - TIP[1]], -1)
    along = rel[..., 0] * DIR[0] + rel[..., 1] * DIR[1]
    perp = np.abs(-rel[..., 0] * DIR[1] + rel[..., 1] * DIR[0])
    cut = (along >= 0) & (along <= TRIM) & (perp < 9)
    out = cover.copy()
    out[cut] = 0
    # round off the new tip so it doesn't end in a raw slice
    cap_c = TIP + DIR * TRIM
    out[((xx - cap_c[0])**2 + (yy - cap_c[1])**2) <= CAP_R**2] = 1.0
    return out


def field(hexbg, hexgrid, blur=0.6):
    img = Image.new('RGB', (W, H), hexbg)
    if hexgrid:
        d = ImageDraw.Draw(img)
        for x in range(0, W, 73):
            d.line([(x, 0), (x, H)], fill=hexgrid, width=2)
        for y in range(63, H, 73):
            d.line([(0, y), (W, y)], fill=hexgrid, width=2)
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(img).astype(np.float32) / 255


def art(cover, bg, ink):
    return np.clip(bg * (1 - cover[..., None]) + hex2rgb(ink) * cover[..., None], 0, 1)


cover = shorten_needle(ink_mask())

# 1. sky field, oxblood art
flat_sky = art(cover, field(SKY, None), OXBLOOD)
Image.fromarray((flat_sky * 255).round().astype(np.uint8)).save('assets/logo-glp-oxblood-sky-flat.png')

# 2. sky field with grid
gridded = art(cover, field(SKY, GRID), OXBLOOD)

# 3. apricot frame around the sky field
inner = Image.fromarray((gridded * 255).round().astype(np.uint8))
frame = Image.new('RGB', (W, H), APRICOT)
mask = Image.new('L', (W - 2 * BORDER, H - 2 * BORDER), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 2 * BORDER - 1, H - 2 * BORDER - 1], radius=30, fill=255)
frame.paste(inner.crop((BORDER, BORDER, W - BORDER, H - BORDER)), (BORDER, BORDER), mask)
frame.save('assets/logo-glp-apricot-frame-oxblood.png')

# 4. transparent artwork for other surfaces
rgba = np.zeros((H, W, 4), np.uint8)
rgba[..., 0:3] = (0x82, 0x24, 0x1F)
rgba[..., 3] = (np.clip(cover, 0, 1) * 255).round().astype(np.uint8)
Image.fromarray(rgba, 'RGBA').save('assets/logo-glp-oxblood-transparent.png')

print("needle trimmed: %.0fpx removed, %.0fpx rounded cap" % (TRIM, CAP_R))
print("saved: apricot-frame, sky-flat, transparent")
