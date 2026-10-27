"""Reads the physical scoreboard that is visible in the panorama.

Gives: the game clock (so stoppages and period starts and ends are known exactly),
score changes (goals), the period digit, and whether the penalty boxes are lit.
Every number it is not sure about is marked so a person can check it.
"""
import json, os, re
from collections import Counter
import numpy as np
import cv2


def _crop(frame, box, pad=0):
    x1, y1, x2, y2 = box
    return frame[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]


def lit_mask(c):
    c = c.astype(np.float32)
    return (np.clip((c[:, :, 2] - 150) / 80.0, 0, 1) * np.clip((c[:, :, 2] - c[:, :, 0] + 10) / 50.0, 0, 1))


def signature(c, w=8, h=12):
    """Tiny picture of the lit part of a digit box, as 0 to 9 numbers."""
    m = cv2.resize(lit_mask(c), (w, h), interpolation=cv2.INTER_AREA)
    return "".join(str(int(round(v * 9))) for v in m.reshape(-1))


def lit_fraction(c):
    c = c.astype(np.float32)
    on = (c[:, :, 2] > 130) & (c[:, :, 2] > 1.5 * c[:, :, 1] + 20)
    return float(on.mean())


def _variants(c):
    a = cv2.resize(c, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    b = cv2.resize(c, None, fx=8, fy=8, interpolation=cv2.INTER_LANCZOS4)
    b = cv2.addWeighted(b, 1.6, cv2.GaussianBlur(b, (0, 0), 3), -0.6, 0)
    return [a, b]


def read_series(video, rink_json, outdir, step=1.0, start=0.0, end=None, reader=None, log=print):
    """Writes scoreboard.jsonl, one line per sample, and can be resumed."""
    cfg = json.load(open(rink_json))["scoreboard"]
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    meta = json.load(open(os.path.join(outdir, "meta.json"))) if os.path.exists(os.path.join(outdir, "meta.json")) else {}
    ref_w = json.load(open(rink_json)).get("width", W)
    sx = W / float(ref_w)
    sc = lambda b: [int(round(v * sx)) for v in b]
    end = min(end if end is not None else total, total)
    path = os.path.join(outdir, "scoreboard.jsonl")
    t = start
    if os.path.exists(path):
        last = None
        for line in open(path):
            try:
                last = json.loads(line)["t"]
            except Exception:
                pass
        if last is not None:
            t = max(t, last + step)
    if reader is None:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=_has_gpu(), verbose=False)
    out = open(path, "a")
    n = 0
    while t < end:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = cap.read()
        if not ok:
            break
        rec = {"t": round(t, 2)}
        cl = _crop(f, sc(cfg["clock"]))
        reads = []
        for v in _variants(cl):
            try:
                res = reader.readtext(v, allowlist="0123456789:.", detail=0, paragraph=False)
            except Exception:
                res = []
            reads.append(re.sub(r"[^0-9]", "", "".join(res)))
        rec["clock"] = reads
        rec["clock_sig"] = signature(cl, 16, 8)
        for k in ("home", "visitor", "period"):
            rec[k] = signature(_crop(f, sc(cfg[k])))
        rec["penh"] = [round(lit_fraction(_crop(f, sc(b))), 3) for b in cfg["pen_home"]]
        rec["penv"] = [round(lit_fraction(_crop(f, sc(b))), 3) for b in cfg["pen_visitor"]]
        out.write(json.dumps(rec) + "\n")
        out.flush()
        n += 1
        if n % 60 == 0:
            log("Scoreboard: %.0f of %.0f s" % (t, end))
        t += step
    out.close()
    return path


def _has_gpu():
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def to_seconds(s):
    """'955' -> 9:55 -> 595. '1000' -> 600. Anything that is not a clock returns None."""
    if len(s) == 3:
        m, ss = int(s[0]), int(s[1:])
    elif len(s) == 4:
        m, ss = int(s[:2]), int(s[2:])
    else:
        return None
    if ss > 59 or m > 30:
        return None
    return m * 60 + ss


def read_back(path):
    rows = []
    for line in open(path):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    rows.sort(key=lambda r: r["t"])
    return rows


def repair_clock(rows, step=1.0):
    """Votes between the readings, then uses the fact that the clock only counts down
    (and jumps back up only when a new period starts) to fix the odd wrong digit.
    Returns [{t, sec, ok}] where ok is False for a guessed value."""
    out = []
    last = None  # last accepted [t, sec]
    for r in rows:
        cands = [to_seconds(s) for s in r["clock"] if s]
        cands = [c for c in cands if c is not None]
        pick, ok = None, False
        if last is not None:
            dt = r["t"] - last[0]
            window = [c for c in cands if last[1] - dt - 2 <= c <= last[1]]
            if window:
                pick = Counter(window).most_common(1)[0][0]
                ok = len(window) == len(cands) or Counter(window).most_common(1)[0][1] >= 2
            else:
                # a new period resets the clock upward
                ups = [c for c in cands if c >= 420 and last[1] <= 150]
                if ups:
                    pick, ok = Counter(ups).most_common(1)[0][0], False
                else:
                    pick = last[1] if dt < 3 else None  # keep the last value for a short blip
                    ok = False
        else:
            if cands:
                pick = Counter(cands).most_common(1)[0][0]
                ok = len(set(cands)) == 1
        if pick is not None:
            if ok or last is None or pick != last[1]:
                last = [r["t"], pick]
            out.append({"t": r["t"], "sec": pick, "ok": bool(ok)})
        else:
            out.append({"t": r["t"], "sec": None, "ok": False})
    return out


def clock_events(clock, step=1.0, min_still=3.0, full_min=420):
    """From the repaired clock: stoppages (clock not moving), and period starts and ends."""
    pts = [c for c in clock if c["sec"] is not None]
    stops, periods = [], []
    i = 0
    while i < len(pts):
        j = i
        while j + 1 < len(pts) and pts[j + 1]["sec"] == pts[i]["sec"]:
            j += 1
        if pts[j]["t"] - pts[i]["t"] + step >= min_still:
            stops.append([pts[i]["t"], pts[j]["t"] + step, pts[i]["sec"]])
        i = j + 1
    # period start: the clock first leaves a full value, going down. period end: it reaches 0:00 or jumps back up
    cur = None
    prev = None
    for p in pts:
        if prev is not None:
            if p["sec"] > prev["sec"] + 30 and p["sec"] >= full_min:
                if cur is not None:
                    cur["end"] = prev["t"] + step
                    cur["end_sec"] = prev["sec"]
                    periods.append(cur)
                    cur = None
            if cur is None and p["sec"] < prev["sec"] and prev["sec"] >= full_min - 20:
                cur = {"start": prev["t"], "start_sec": prev["sec"]}
        elif p["sec"] >= full_min - 20:
            pass
        prev = p
    if cur is not None:
        cur["end"] = pts[-1]["t"] + step
        cur["end_sec"] = pts[-1]["sec"]
        cur["open"] = True
        periods.append(cur)
    return stops, periods


def _norm_diff(a, b):
    return float(np.abs(a - b).sum() / (a.sum() + b.sum() + 1e-6))


def changes(rows, key, thresh=0.16, hold=4):
    """Times when a digit box shows a different, steady picture (the score or period changed).
    The same digit differs by at most about 0.10 from picture to picture, a different digit by far more."""
    ev = []
    sig = [np.array([int(c) for c in r[key]], dtype=np.float32) for r in rows]
    if len(sig) < hold:
        return ev
    cur = np.median(np.array(sig[:3]), axis=0)
    i = 0
    while i < len(sig):
        d = _norm_diff(sig[i], cur)
        if d > thresh:
            run = [k for k in range(i, min(len(sig), i + hold)) if _norm_diff(sig[k], sig[i]) < thresh]
            if len(run) >= hold and all(_norm_diff(sig[k], cur) > thresh for k in run):
                ev.append({"t": rows[i]["t"], "diff": round(d, 2), "clear": bool(d >= 0.30)})
                cur = np.median(np.array(sig[i:i + hold]), axis=0)
                i += hold
                continue
        i += 1
    return ev


def penalty_runs(rows, key, min_len=3.0, thresh=0.04):
    """For one penalty box row: when is it lit. A lit box means a penalty time is showing."""
    out = {0: [], 1: []}
    for row in (0, 1):
        on = None
        for r in rows:
            v = r[key][row]
            if v >= thresh and on is None:
                on = r["t"]
            elif v < thresh and on is not None:
                if r["t"] - on >= min_len:
                    out[row].append([on, r["t"]])
                on = None
        if on is not None and rows and rows[-1]["t"] - on >= min_len:
            out[row].append([on, rows[-1]["t"]])
    return out


def analyze(path, step=1.0):
    rows = read_back(path)
    clock = repair_clock(rows, step)
    stops, periods = clock_events(clock, step)
    return {
        "clock": clock, "stops": stops, "periods": periods,
        "home_changes": changes(rows, "home"), "visitor_changes": changes(rows, "visitor"),
        "period_changes": changes(rows, "period"),
        "pen_home": penalty_runs(rows, "penh"), "pen_visitor": penalty_runs(rows, "penv"),
        "samples": len(rows),
    }
