"""The Kings caption graphic for highlight clips: a purple and silver broadcast lower third, drawn with Pillow
and laid over the video with ffmpeg. Names and numbers come from the Kings Film Room roster."""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
PURPLE, PURPLE_DK, PANEL = (74, 52, 135), (46, 30, 94), (18, 14, 36)
SILVER, ACCENT, WHITE = (190, 190, 196), (155, 124, 255), (243, 244, 251)


def _font(weight, px):
    for p in (os.path.join(FONTS, "BarlowCondensed-%s.ttf" % weight), "C:/Windows/Fonts/bahnschrift.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, max(8, int(px)))
        except Exception:
            continue
    return ImageFont.load_default()


def _w(d, text, font, spacing=0):
    return d.textlength(text, font=font) + spacing * max(0, len(text) - 1)


def _spaced(d, xy, text, font, fill, spacing):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + spacing


def _fit(d, text, weight, px, max_w):
    """Largest font up to px that fits the width."""
    while px > 18:
        f = _font(weight, px)
        if d.textlength(text, font=f) <= max_w:
            return f
        px -= 2
    return _font(weight, 18)


def _logo(h):
    p = os.path.join(FONTS, "kings-logo.png")
    try:
        im = Image.open(p).convert("RGBA")
        return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    except Exception:
        return None


def lower_third(path, scale, tag, num, name, sub=None):
    """Draws the caption to a transparent PNG. tag is the small top line (GOAL, SAVE, BACK CHECK),
    num the jersey number or None, name the player's name or None, sub a line under the name."""
    s = scale
    H = int((196 if sub else 150) * s)
    pad = int(14 * s)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    f_tag = _font("700", 30 * s)
    f_num = _font("800", 104 * s)
    f_name = _font("800", 70 * s)
    f_sub = _font("600", 34 * s)
    text_w = max(_w(d0, tag.upper(), f_tag, 4 * s) + 40 * s,
                 _w(d0, (name or "").upper(), f_name, 1 * s),
                 _w(d0, (sub or "").upper(), f_sub, 1 * s))
    num_w = int(190 * s) if num else int(30 * s)
    logo = _logo(int(112 * s))
    logo_w = (logo.width + int(36 * s)) if logo else 0
    W = int(num_w + 30 * s + text_w + logo_w + 40 * s + pad)
    im = Image.new("RGBA", (W, H + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top, bot = 0, H
    slant = int(26 * s)
    # dark panel behind everything, slanted at the right end
    d.polygon([(num_w - slant, top), (W - pad, top), (W - pad - slant, bot), (num_w - 2 * slant, bot)], fill=PANEL + (238,))
    # silver edge along the bottom of the panel
    d.polygon([(num_w - 2 * slant, bot - int(6 * s)), (W - pad - slant, bot - int(6 * s)), (W - pad - slant, bot), (num_w - 2 * slant, bot)], fill=SILVER + (255,))
    # purple number block
    d.polygon([(0, top), (num_w, top), (num_w - slant, bot), (0, bot)], fill=PURPLE + (255,))
    d.polygon([(0, top), (int(14 * s), top), (int(14 * s), bot), (0, bot)], fill=SILVER + (255,))
    if num:
        t = str(num)
        f = _fit(d, t, "800", 104 * s, num_w - 70 * s)
        tw = d.textlength(t, font=f)
        bb = f.getbbox(t)
        d.text(((num_w - slant / 2 - tw) / 2 + 6 * s, (H - (bb[3] - bb[1])) / 2 - bb[1]), t, font=f, fill=WHITE + (255,))
    x0 = num_w + 10 * s
    # tag chip
    chip_h = int(40 * s)
    tw = _w(d, tag.upper(), f_tag, 4 * s)
    d.rectangle([x0, int(16 * s), x0 + tw + 28 * s, int(16 * s) + chip_h], fill=ACCENT + (255,))
    _spaced(d, (x0 + 14 * s, int(16 * s) + (chip_h - f_tag.size) / 2 - 3 * s), tag.upper(), f_tag, PANEL + (255,), 4 * s)
    # name and sub line
    ny = int(16 * s) + chip_h + int(2 * s)
    if name:
        d.text((x0, ny), name.upper(), font=f_name, fill=WHITE + (255,))
        if sub:
            d.text((x0 + 2 * s, ny + f_name.size * 1.0), sub.upper(), font=f_sub, fill=SILVER + (255,))
    elif sub:
        d.text((x0, ny), sub.upper(), font=f_sub, fill=SILVER + (255,))
    if logo:
        im.alpha_composite(logo, (int(W - pad - slant - logo.width - 18 * s), int((H - logo.height) / 2)))
    im.save(path)
    return im.size


def angle_chip(path, scale, text, replay=True):
    """Small chip for the top left corner: MAIN CAM, or REPLAY plus the camera name."""
    s = scale
    f = _font("700", 34 * s)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    label = text.upper()
    tw = _w(d0, label, f, 4 * s)
    pad = int(18 * s)
    rtw = _w(d0, "REPLAY", f, 3 * s) + 2 * pad if replay else 0
    W, H = int(tw + pad * 2 + rtw), int(54 * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 0
    if replay:
        rw = int(rtw)
        d.rectangle([0, 0, rw, H], fill=ACCENT + (255,))
        _spaced(d, (pad, (H - f.size) / 2 - 3 * s), "REPLAY", f, PANEL + (255,), 3 * s)
        x = rw
    d.rectangle([x, 0, W, H], fill=PANEL + (225,))
    d.rectangle([0, H - int(4 * s), W, H], fill=SILVER + (255,))
    _spaced(d, (x + pad, (H - f.size) / 2 - 3 * s), label, f, WHITE + (255,), 4 * s)
    im.save(path)
    return im.size


def score_bug(path, scale, us_name, us, them_name, them, scored="us"):
    """Score bug for the top right corner: Kings on the left, the other team on the right.
    scored is "us" or "them": the side that just scored gets the lit score box."""
    s = scale
    H = int(84 * s)
    f_name = _font("700", 40 * s)
    f_sc = _font("800", 64 * s)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    pad = int(20 * s)
    max_name = int(380 * s)
    f_opp = _fit(d0, them_name.upper(), "700", 40 * s, max_name)
    opp_txt = them_name.upper()
    while d0.textlength(opp_txt, font=f_opp) > max_name and len(opp_txt) > 4:
        opp_txt = opp_txt[:-2].rstrip()
    us_w = int(_w(d0, us_name.upper(), f_name, 2 * s) + pad * 2)
    opp_w = int(_w(d0, opp_txt, f_opp, 2 * s) + pad * 2)
    box = int(84 * s)
    W = us_w + box * 2 + opp_w
    im = Image.new("RGBA", (W, H + int(6 * s)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, us_w, H], fill=PURPLE + (255,))
    d.rectangle([us_w, 0, us_w + box, H], fill=(ACCENT if scored == "us" else PANEL) + (255,))
    d.rectangle([us_w + box, 0, us_w + 2 * box, H], fill=(ACCENT if scored == "them" else PANEL) + (255,))
    d.rectangle([us_w + 2 * box, 0, W, H], fill=PANEL + (240,))
    d.rectangle([0, H, W, H + int(6 * s)], fill=SILVER + (255,))
    _spaced(d, (pad, (H - f_name.size) / 2 - 4 * s), us_name.upper(), f_name, WHITE + (255,), 2 * s)
    _spaced(d, (us_w + 2 * box + pad, (H - f_opp.size) / 2 - 4 * s), opp_txt, f_opp, WHITE + (255,), 2 * s)
    for i, (val, lit) in enumerate(((us, scored == "us"), (them, scored == "them"))):
        t = str(val)
        bb = f_sc.getbbox(t)
        x0 = us_w + i * box
        d.text((x0 + (box - d.textlength(t, font=f_sc)) / 2, (H - (bb[3] - bb[1])) / 2 - bb[1]), t, font=f_sc,
               fill=(PANEL if lit else WHITE) + (255,))
    im.save(path)
    return im.size
