"""Faceoffs, zones and line changes from the one pass results.

Faceoffs: the scoreboard clock starts again after a stop (or a period starts). Where most skaters
are bunched just before that is where the faceoff is. Zone comes from the blue and centre lines
marked in the rink file. Which end is the Kings' attack end is set on the review page.
Line changes: skaters appearing at or leaving the bench boards close together in time.
"""
import json, os
import numpy as np


def _interp(pts, y):
    pts = sorted(pts, key=lambda p: p[1])
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    return float(np.interp(y, ys, xs))


def locate(cfg, x, y):
    """Return (side, zone, u, v). side is L or R end of the rink, zone is E (end) or N (neutral)."""
    ln = cfg["lines"]
    xl = _interp(ln["blue_left"], y)
    xr = _interp(ln["blue_right"], y)
    xc = ln["centre_x"]
    w = cfg["width"]
    if x < xl:
        zone, side = "E", "L"
        u = 0.375 * max(0.0, x) / max(1.0, xl)
    elif x > xr:
        zone, side = "E", "R"
        u = 0.625 + 0.375 * (x - xr) / max(1.0, w - xr)
    else:
        zone, side = "N", ("L" if x < xc else "R")
        u = 0.375 + 0.25 * (x - xl) / max(1.0, xr - xl)
    far, near = 957.0, float(cfg["height"]) + 120.0
    v = min(1.0, max(0.0, (y - far) / (near - far)))
    return side, zone, round(u, 3), round(v, 3)


def _cluster_centre(pts, radius=260.0):
    best, bi = -1, 0
    for i, (x, y) in enumerate(pts):
        n = sum(1 for (a, b) in pts if (a - x) ** 2 + (b - y) ** 2 <= radius ** 2)
        if n > best:
            best, bi = n, i
    x0, y0 = pts[bi]
    near = [(a, b) for (a, b) in pts if (a - x0) ** 2 + (b - y0) ** 2 <= radius ** 2]
    return float(np.mean([p[0] for p in near])), float(np.mean([p[1] for p in near])), best


def faceoffs(rows, board, cfg):
    """One entry per clock restart. rows are detections rows [{t, d:[...]}]."""
    out = []
    marks = []
    for a, b, _s in (board or {}).get("stops", []):
        marks.append((float(b), "restart"))
    for p in (board or {}).get("periods", []):
        marks.append((float(p.get("start", 0)), "period"))
    marks.sort()
    seen = []
    for t, kind in marks:
        if any(abs(t - s) < 4 for s in seen):
            continue
        seen.append(t)
        cand = [r for r in rows if t - 6 <= r["t"] <= t + 0.5 and r.get("d")]
        if not cand:
            cand = [r for r in rows if t - 40 <= r["t"] <= t + 3 and r.get("d")]
        entry = {"t": max(0.0, t - 1.0), "kind": kind, "flag": "no skaters seen"}
        if cand:
            r = cand[-1]
            pts = [((d[0] + d[2]) / 2.0, float(d[3])) for d in r["d"]]
            pts = [p for p in pts if p[1] > 0]
            if len(pts) >= 3:
                x, y, n = _cluster_centre(pts)
                side, zone, u, v = locate(cfg, x, y)
                entry.update({"x": round(x), "y": round(y), "side": side, "zone": zone,
                              "u": u, "v": v, "n": n, "flag": "" if n >= 4 else "few skaters bunched"})
        out.append(entry)
    return out


def changes(rows, labels, outdir, tracks, cfg, gap=8.0, band=110.0):
    """Moments when skaters appear at, or vanish into, the bench boards. Needs bench.jsonl."""
    p = os.path.join(outdir, "bench.jsonl")
    if not os.path.exists(p):
        return []
    import onepass
    fx, fy = onepass.far_edge(np.array(cfg["ice"], dtype=float))
    bench = []
    for line in open(p):
        try:
            bench.append(json.loads(line))
        except Exception:
            pass
    pts = []  # (t, group, x, y, kind)
    for tr in tracks:
        for k, q in (("on", tr["pts"][0]), ("off", tr["pts"][-1])):
            edge = float(np.interp(q[1], fx, fy))
            if q[2] - edge < band:
                pts.append((q[0], tr["g"], q[1], q[2], k))
    pts.sort()
    groups, cur = [], []
    for e in pts:
        if cur and e[0] - cur[-1][0] > gap:
            groups.append(cur)
            cur = []
        cur.append(e)
    if cur:
        groups.append(cur)
    out = []
    for gp in groups:
        thumbs = {}
        for (t, g, x, y, k) in gp:
            near = [b for b in bench if abs(b["t"] - t) <= 2.0 and abs(b["x"] - x) < 90]
            if not near:
                continue
            b = min(near, key=lambda b: abs(b["t"] - t) + abs(b["x"] - x) / 100.0)
            lst = thumbs.setdefault(str(g), [])
            if len(lst) < 6 and b["img"] not in lst:
                lst.append(b["img"])
        out.append({"t0": gp[0][0], "t1": gp[-1][0], "thumbs": thumbs,
                    "on": sum(1 for e in gp if e[4] == "on"), "off": sum(1 for e in gp if e[4] == "off")})
    return out
