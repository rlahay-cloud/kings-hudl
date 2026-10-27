"""Tries to read jersey numbers for each followed box. Every answer carries how many
pictures agreed, so the review page can show it as sure, maybe, or not readable."""
import re
from collections import defaultdict
import numpy as np
import cv2


def _prep(frame, box, big=240):
    x1, y1, x2, y2 = box
    h, w = y2 - y1, x2 - x1
    ya, yb = int(y1 + 0.08 * h), int(y1 + 0.66 * h)
    xa, xb = int(x1 - 0.08 * w), int(x2 + 0.08 * w)
    c = frame[max(0, ya):yb, max(0, xa):xb]
    if c.size == 0:
        return None
    s = big / float(c.shape[0])
    c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    return c


def _read(reader, img):
    """Returns [(digits, confidence)] for text that is only digits."""
    out = []
    try:
        res = reader.readtext(img, allowlist="0123456789", detail=1, paragraph=False,
                              text_threshold=0.5, low_text=0.3, mag_ratio=1.0)
    except Exception:
        return out
    items = []
    for box, txt, conf in res:
        t = re.sub(r"[^0-9]", "", txt)
        if not t:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append((min(xs), (min(ys) + max(ys)) / 2.0, t, float(conf), max(ys) - min(ys)))
    items.sort()
    # join digits that sit side by side on one line, e.g. "1" then "7"
    used = [False] * len(items)
    for i, it in enumerate(items):
        if used[i]:
            continue
        txt, conf, n = it[2], it[3], 1
        used[i] = True
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            if abs(items[j][1] - it[1]) < 0.5 * max(it[4], items[j][4]) and len(txt) < 2:
                txt += items[j][2]
                conf += items[j][3]
                n += 1
                used[j] = True
        out.append((txt[:3], conf / n))
    return out


def _variants(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(g)
    out = []
    for base in (img, cl):
        out.append(base)
        out.append(cv2.rotate(base, cv2.ROTATE_90_CLOCKWISE))
        out.append(cv2.rotate(base, cv2.ROTATE_90_COUNTERCLOCKWISE))
    return out


def read_track(frames, reader, roster=None, max_samples=6):
    """frames: [(frame_image, box, h)] for one track. Tries each picture upright and turned
    sideways (numbers on sleeves run up and down), plain and with extra contrast."""
    votes = defaultdict(float)
    count = defaultdict(int)
    tried = 0
    for fr, box, h in frames[:max_samples]:
        img = _prep(fr, box)
        if img is None:
            continue
        tried += 1
        seen = set()
        for v in _variants(img):
            for txt, conf in _read(reader, v):
                if len(txt) > 2 or int(txt) > 99 or conf < 0.30:
                    continue
                if txt in seen:
                    continue  # one vote per picture per number
                seen.add(txt)
                votes[txt] += conf
                count[txt] += 1
    if not votes:
        return {"best": None, "level": "none", "tried": tried, "cands": []}
    ranked = sorted(votes.items(), key=lambda kv: (-count[kv[0]], -kv[1]))
    cands = [{"n": n, "votes": count[n], "score": round(v, 2),
              "roster": bool(roster and int(n) in roster)} for n, v in ranked[:3]]
    best = cands[0]
    if roster:
        inr = [c for c in cands if c["roster"]]
        if inr and not best["roster"] and inr[0]["votes"] >= best["votes"] - 1:
            best = inr[0]
    if best["votes"] >= 3:
        level = "good"
    elif best["votes"] >= 2:
        level = "maybe"
    else:
        level = "weak"
    return {"best": best["n"], "level": level, "tried": tried, "cands": cands}
