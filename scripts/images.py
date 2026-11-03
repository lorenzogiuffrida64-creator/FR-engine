"""Image operations: crops for the per-player edit, blending back, contact sheets, grids,
delivery formats with the AI tag, and the measurable QC checks (kit colour, unchanged edits)."""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from common import CFG

Image.MAX_IMAGE_PIXELS = 80_000_000  # refuse decompression bombs


def open_rgb(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def font(size):
    return ImageFont.load_default(size=size)


# ---------- per-player crop and blend ----------

def bbox_px(bbox, size):
    W, H = size
    x0, y0, x1, y1 = bbox
    return int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)


def padded_box(bbox, size, pad):
    """Pad a fractional bbox on every side by pad × its size, clamp to the image. Returns pixel box."""
    x0, y0, x1, y1 = bbox_px(bbox, size)
    w, h = x1 - x0, y1 - y0
    W, H = size
    return (max(0, int(x0 - pad * w)), max(0, int(y0 - pad * h)),
            min(W, int(x1 + pad * w)), min(H, int(y1 + pad * h)))


def crop_for_edit(img, bbox, pad, min_side, dest):
    box = padded_box(bbox, img.size, pad)
    crop = img.crop(box)
    scale = max(1.0, min_side / min(crop.size))
    if scale > 1:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    crop.save(dest, quality=95)
    return box


def blend_back(img, edited_path, box, feather=0.06):
    """Paste the edited crop over box with a feathered edge so the seam disappears."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    patch = open_rgb(edited_path).resize((w, h), Image.LANCZOS)
    f = max(2, int(min(w, h) * feather))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle([f, f, w - f - 1, h - f - 1], fill=255)
    # don't feather the edges that touch the image border: there is nothing to blend into
    W, H = img.size
    d = ImageDraw.Draw(mask)
    if x0 == 0: d.rectangle([0, 0, f, h], fill=255)
    if y0 == 0: d.rectangle([0, 0, w, f], fill=255)
    if x1 == W: d.rectangle([w - f - 1, 0, w, h], fill=255)
    if y1 == H: d.rectangle([0, h - f - 1, w, h], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(f / 2))
    out = img.copy()
    out.paste(patch, (x0, y0), mask)
    return out


def mean_abs_diff(a_path, b_img, box=None):
    """How much an edit changed a region (0–255 scale). Used to catch silent refusals."""
    a = open_rgb(a_path)
    b = b_img.resize(a.size, Image.LANCZOS) if b_img.size != a.size else b_img
    if box:
        a, b = a.crop(box), b.crop(box)
    return float(np.abs(np.asarray(a, np.float32) - np.asarray(b, np.float32)).mean())


# ---------- sheets ----------

def contact_sheet(items, dest, title, cols=4, cell=(300, 400)):
    """items: [(label, path)]. Numbered grid for picking."""
    W, H = cell; pad, cap = 10, 30
    rows = -(-len(items) // cols)
    sheet = Image.new("RGB", (cols * (W + pad) + pad, rows * (H + pad + cap) + pad + 34), (245, 241, 232))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), title, fill=(23, 23, 18), font=font(18))
    for i, (label, path) in enumerate(items):
        x = pad + (i % cols) * (W + pad); y = 34 + pad + (i // cols) * (H + pad + cap)
        im = open_rgb(path); im.thumbnail((W, H))
        sheet.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        d.rectangle([x, y + H + 3, x + 64, y + H + 27], fill=(23, 23, 18))
        d.text((x + 8, y + H + 5), str(label), fill=(245, 241, 232), font=font(18))
    sheet.save(dest, quality=85)
    return dest


def grid_overlay(src, dest, step=0.1):
    """Draw labelled gridlines (fractions) so bboxes can be read off the image."""
    im = open_rgb(src)
    d = ImageDraw.Draw(im)
    W, H = im.size
    f = font(max(14, W // 60))
    for i in range(1, int(1 / step)):
        x, y = int(i * step * W), int(i * step * H)
        d.line([(x, 0), (x, H)], fill=(255, 40, 40), width=2)
        d.line([(0, y), (W, y)], fill=(255, 40, 40), width=2)
        d.text((x + 4, 4), f"{i * step:.1f}", fill=(255, 255, 0), font=f)
        d.text((4, y + 4), f"{i * step:.1f}", fill=(255, 255, 0), font=f)
    im.save(dest, quality=90)
    return dest


# ---------- delivery ----------

def fit_crop(img, target, focus=(0.5, 0.42)):
    """Crop to the target ratio around a focus point (fractions), then resize."""
    tw, th = target
    W, H = img.size
    r = tw / th
    if W / H > r:
        nw, nh = int(H * r), H
    else:
        nw, nh = W, int(W / r)
    cx, cy = focus[0] * W, focus[1] * H
    x0 = int(min(max(cx - nw / 2, 0), W - nw)); y0 = int(min(max(cy - nh / 2, 0), H - nh))
    return img.crop((x0, y0, x0 + nw, y0 + nh)).resize((tw, th), Image.LANCZOS)


def ai_tag(img):
    t = CFG["delivery"]["ai_tag"]
    im = img.convert("RGBA")
    W, H = im.size
    size = max(14, int(min(W, H) * t["size"]))
    f = font(size)
    l, top, r, b = f.getbbox(t["text"])
    pw, ph = r - l + size, b - top + size // 2
    m = int(min(W, H) * 0.025)
    x = W - pw - m if "right" in t["corner"] else m
    y = H - ph - m if "bottom" in t["corner"] else m
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x, y, x + pw, y + ph], radius=ph // 2, fill=(0, 0, 0, int(255 * t["opacity"] * 0.7)))
    d.text((x + size // 2 - l, y + size // 4 - top), t["text"], fill=(255, 255, 255, int(255 * t["opacity"])), font=f)
    return Image.alpha_composite(im, layer).convert("RGB")


# ---------- QC: kit colour ----------

def _srgb_to_lab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]  # explicit sums: numpy's matmul warns spuriously on macOS
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    xyz = np.stack([x, y, z], -1)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def hex_lab(h):
    h = h.lstrip("#")
    return _srgb_to_lab(np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)]]))[0]


def delta_e(hex_a, hex_b):
    return float(np.linalg.norm(hex_lab(hex_a) - hex_lab(hex_b)))


def kit_coverage(img, bbox, colours):
    """Share of the torso band (inside the player's bbox) that matches each kit colour.
    Shirts sit in light and shadow, so saturated colours match on hue (and enough chroma), not on
    lightness; white/black/grey kit colours match on lightness with low chroma."""
    x0, y0, x1, y1 = bbox_px(bbox, img.size)
    w, h = x1 - x0, y1 - y0
    torso = img.crop((x0 + int(0.2 * w), y0 + int(0.28 * h), x1 - int(0.2 * w), y0 + int(0.55 * h)))
    torso.thumbnail((160, 160))
    lab = _srgb_to_lab(np.asarray(torso)).reshape(-1, 3)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    hue = np.degrees(np.arctan2(lab[:, 2], lab[:, 1]))
    q = CFG["qc"]
    out = {}
    for name, hx in colours.items():
        ref = hex_lab(hx); ref_c = np.hypot(ref[1], ref[2])
        if ref_c < q["kit_neutral_chroma"]:
            hit = (chroma < q["kit_neutral_chroma"] + 3) & (np.abs(lab[:, 0] - ref[0]) < q["kit_neutral_lightness"])
        else:
            dh = np.abs((hue - np.degrees(np.arctan2(ref[2], ref[1])) + 180) % 360 - 180)
            hit = (dh < q["kit_hue_degrees"]) & (chroma > 0.3 * ref_c)
        out[name] = round(float(hit.mean()), 3)
    return out


# ---------- QC: face similarity (optional dependency) ----------

_FACE_APP = None


def face_similarity(img_path, bbox, ref_paths):
    """Cosine similarity between the face inside bbox and the reference faces, using insightface if present.
    Returns None when insightface is not installed (Claude does the check by eye instead)."""
    global _FACE_APP
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        return None
    if _FACE_APP is None:
        _FACE_APP = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _FACE_APP.prepare(ctx_id=0, det_size=(640, 640))

    def emb(im):
        faces = _FACE_APP.get(np.asarray(im)[:, :, ::-1])
        if not faces:
            return None
        f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return f.normed_embedding

    img = open_rgb(img_path)
    target = emb(img.crop(padded_box(bbox, img.size, 0.1)))
    refs = [e for e in (emb(open_rgb(p)) for p in ref_paths) if e is not None]
    if target is None or not refs:
        return 0.0
    return round(float(max(np.dot(target, r) for r in refs)), 3)
