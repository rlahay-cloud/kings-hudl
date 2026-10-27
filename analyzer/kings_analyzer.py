#!/usr/bin/env python3
"""Kings HUDL game analyzer, version 1.

Step 1 (detect):  finds every skater on the ice in a wide panorama video, a few times a second.
Step 2 (build):   follows them, groups them by jersey colour, and writes a review page where a
                  person names each box once. The page exports shifts in the same text format
                  the Shifts tab already uses.

Plain steps:  python kings_analyzer.py detect VIDEO OUTDIR --rink rinks/ingredion_rink1.json
              python kings_analyzer.py build  VIDEO OUTDIR --rink rinks/ingredion_rink1.json
"""
import argparse, base64, json, math, os, sys, time
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TILE_W = 1600
TILE_STRIDE = 1240


def load_rink(path, w, h):
    r = json.load(open(path))
    sx, sy = w / float(r["width"]), h / float(r["height"])
    poly = np.array([[p[0] * sx, p[1] * sy] for p in r["ice"]], dtype=np.float32)
    return r["name"], poly


def on_ice(poly, x, y, margin=0):
    return cv2.pointPolygonTest(poly.reshape(-1, 1, 2), (float(x), float(y)), True) >= -margin


def tiles_for(width, y0, y1):
    xs = [0]
    while xs[-1] + TILE_W < width:
        xs.append(min(xs[-1] + TILE_STRIDE, width - TILE_W))
    return [(x, y0, TILE_W, y1 - y0) for x in xs]


def torso_rgb(frame, x1, y1, x2, y2):
    """Median colour of the chest plus how much of it is blue, white and dark."""
    h, w = y2 - y1, x2 - x1
    ya, yb = int(y1 + 0.20 * h), int(y1 + 0.55 * h)
    xa, xb = int(x1 + 0.20 * w), int(x2 - 0.20 * w)
    c = frame[max(ya, 0):max(yb, ya + 1), max(xa, 0):max(xb, xa + 1)]
    if c.size == 0:
        return [128, 128, 128, 0, 0, 0]
    px = c.reshape(-1, 3)
    m = np.median(px, axis=0)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int32)
    hh, ss, vv = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    n = float(len(hsv))
    blue = np.sum((hh >= 95) & (hh <= 135) & (ss > 55) & (vv > 50)) / n
    white = np.sum((ss < 45) & (vv > 150)) / n
    dark = np.sum(vv < 70) / n
    return [int(m[2]), int(m[1]), int(m[0]), int(round(blue * 100)), int(round(white * 100)), int(round(dark * 100))]


def nms(boxes, scores, thr=0.45):
    if not boxes:
        return []
    b = np.array(boxes, dtype=np.float32)
    idx = cv2.dnn.NMSBoxes([[float(x[0]), float(x[1]), float(x[2] - x[0]), float(x[3] - x[1])] for x in b],
                           [float(s) for s in scores], 0.0, thr)
    return [int(i) for i in np.array(idx).reshape(-1)]


def detect(video, outdir, rink, step=0.5, start=0.0, end=None, imgsz=1280, conf=0.25,
           limit=None, model_path="yolov8s.pt", device=None, log=print):
    from ultralytics import YOLO
    os.makedirs(outdir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    end = min(end if end is not None else total, total)
    name, poly = load_rink(rink, W, H)
    y0 = max(0, int(poly[:, 1].min()) - 130)
    tiles = tiles_for(W, y0, H)
    path = os.path.join(outdir, "detections.jsonl")
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
            log("Resuming at %.1f s" % t)
    meta = {"video": os.path.basename(video), "w": W, "h": H, "fps": fps, "step": step, "rink": name,
            "duration": total}
    json.dump(meta, open(os.path.join(outdir, "meta.json"), "w"))
    model = YOLO(model_path)
    out = open(path, "a")
    stride = max(1, int(round(step * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    done, t0 = 0, time.time()
    while t < end:
        ok, frame = cap.read()
        if not ok:
            break
        crops = [frame[y:y + h, x:x + w] for (x, y, w, h) in tiles]
        res = model.predict(crops, imgsz=imgsz, conf=conf, classes=[0], verbose=False, device=device)
        boxes, scores = [], []
        for (tx, ty, _, _), r in zip(tiles, res):
            for b, s in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
                x1, y1, x2, y2 = b[0] + tx, b[1] + ty, b[2] + tx, b[3] + ty
                bw, bh = x2 - x1, y2 - y1
                if bh < 18 or bh > 300 or bw / bh > 1.8 or bw / bh < 0.18:
                    continue
                if not on_ice(poly, (x1 + x2) / 2, y2):
                    continue
                boxes.append([x1, y1, x2, y2])
                scores.append(float(s))
        keep = nms(boxes, scores)
        dets = []
        for i in keep:
            x1, y1, x2, y2 = boxes[i]
            dets.append([round(x1), round(y1), round(x2), round(y2), round(scores[i], 2)] +
                        torso_rgb(frame, int(x1), int(y1), int(x2), int(y2)))
        out.write(json.dumps({"t": round(t, 2), "d": dets}) + "\n")
        out.flush()
        done += 1
        if done % 20 == 0:
            el = time.time() - t0
            log("%.0f of %.0f s done, %.1f s per picture" % (t, end, el / done))
        if limit and done >= limit:
            break
        t += step
        for _ in range(stride - 1):
            if not cap.grab():
                break
    out.close()
    log("Detection finished: %d pictures" % done)
    return path


# ---------------------------------------------------------------- build step

def read_dets(outdir):
    rows = []
    for line in open(os.path.join(outdir, "detections.jsonl")):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    rows.sort(key=lambda r: r["t"])
    return rows


def rgb_to_lab(rgb):
    a = np.uint8([[rgb]])
    return cv2.cvtColor(a, cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)


def colour_groups(rows, k=4, seed=1):
    from sklearn.cluster import KMeans
    feats, where = [], []
    for ri, r in enumerate(rows):
        for di, d in enumerate(r["d"]):
            feats.append(np.array(d[8:11], dtype=np.float32))
            where.append((ri, di))
    if len(feats) < k * 5:
        return [[0, 0, 0]] * k, {}
    km = KMeans(n_clusters=k, n_init=5, random_state=seed).fit(np.array(feats))
    lab = {w: int(c) for w, c in zip(where, km.labels_)}
    centres = []
    for c in range(k):
        members = [rows[ri]["d"][di][5:8] for (ri, di), l in lab.items() if l == c]
        centres.append([int(x) for x in np.median(np.array(members), axis=0)] if members else [0, 0, 0])
    return centres, lab


def track(rows, labels, step, max_gap=3.0, min_len=1.5):
    from scipy.optimize import linear_sum_assignment
    tracks, active = [], []
    for ri, r in enumerate(rows):
        dets = []
        for di, d in enumerate(r["d"]):
            dets.append({"x": (d[0] + d[2]) / 2.0, "y": float(d[3]), "h": float(d[3] - d[1]),
                         "box": d[:4], "conf": d[4], "g": labels.get((ri, di), 0), "rgb": d[5:8], "ei": (r["e"] + di) if "e" in r else -1})
        t = r["t"]
        active = [a for a in active if t - a["last"] <= max_gap + 1e-6]
        if active and dets:
            cost = np.full((len(active), len(dets)), 1e6)
            for i, a in enumerate(active):
                gate = max(45.0, 2.9 * a["h"] * (t - a["last"]) / 0.5)
                for j, d in enumerate(dets):
                    dist = math.hypot(a["x"] - d["x"], a["y"] - d["y"])
                    if dist <= gate:
                        cost[i, j] = dist + (0 if a["g"] == d["g"] else 60)
            ri_, ci_ = linear_sum_assignment(cost)
            used = set()
            for i, j in zip(ri_, ci_):
                if cost[i, j] < 1e5:
                    a, d = active[i], dets[j]
                    a["pts"].append([t, round(d["x"]), round(d["y"]), round(d["h"]), d["conf"], d["g"]] + d["box"] + [d["ei"]])
                    a["x"], a["y"], a["h"], a["last"], a["g"] = d["x"], d["y"], d["h"], t, d["g"]
                    used.add(j)
            dets = [d for j, d in enumerate(dets) if j not in used]
        for d in dets:
            tr = {"x": d["x"], "y": d["y"], "h": d["h"], "last": t, "g": d["g"],
                  "pts": [[t, round(d["x"]), round(d["y"]), round(d["h"]), d["conf"], d["g"]] + d["box"] + [d["ei"]]]}
            tracks.append(tr)
            active.append(tr)
    out = []
    for tr in tracks:
        p = tr["pts"]
        if len(p) < 3 or p[-1][0] - p[0][0] < min_len:
            continue
        groups = [q[5] for q in p]
        g = max(set(groups), key=groups.count)
        out.append({"id": len(out) + 1, "t0": p[0][0], "t1": p[-1][0], "g": g, "pts": p})
    return out


def stoppages(tracks, step, win=4.0, still=0.30, min_len=5.0):
    """Suggest dead time: nearly everybody on the ice is standing still."""
    if not tracks:
        return []
    tmax = max(t["t1"] for t in tracks)
    n = int(tmax / step) + 2
    speed = [[] for _ in range(n)]
    for tr in tracks:
        p = tr["pts"]
        for a, b in zip(p, p[1:]):
            dt = b[0] - a[0]
            if dt <= 0 or dt > 1.5 * step:
                continue
            v = math.hypot(b[1] - a[1], b[2] - a[2]) / max(a[3], 1) / dt  # body heights per second
            speed[int(b[0] / step)].append(v)
    med = np.array([np.median(s) if len(s) >= 3 else np.nan for s in speed])
    k = max(1, int(win / step))
    sm = np.array([np.nanmedian(med[max(0, i - k // 2):i + k // 2 + 1]) if not np.all(np.isnan(med[max(0, i - k // 2):i + k // 2 + 1])) else np.nan
                   for i in range(n)])
    out, i = [], 0
    while i < n:
        if not np.isnan(sm[i]) and sm[i] < still:
            j = i
            while j + 1 < n and not np.isnan(sm[j + 1]) and sm[j + 1] < still:
                j += 1
            if (j - i + 1) * step >= min_len:
                out.append([round(i * step, 1), round((j + 1) * step, 1)])
            i = j + 1
        else:
            i += 1
    return out


def thumb(frame, box, h_out=150):
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    pad = 0.12
    xa, xb = int(max(0, x1 - pad * bw)), int(min(frame.shape[1], x2 + pad * bw))
    ya, yb = int(max(0, y1 - pad * bh)), int(min(frame.shape[0], y2 + pad * bh))
    c = frame[ya:yb, xa:xb]
    if c.size == 0:
        return ""
    s = h_out / float(c.shape[0])
    c = cv2.resize(c, (max(8, int(c.shape[1] * s)), h_out), interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


def build(video, outdir, rink, k=4, log=print, read_nums=False, min_len=3.0, thumbs=False):
    meta = json.load(open(os.path.join(outdir, "meta.json")))
    rows = read_dets(outdir)
    if not rows:
        raise SystemExit("No detections found in " + outdir)
    step = meta["step"]
    centres, labels = colour_groups(rows, k)
    tracks = track(rows, labels, step, min_len=min_len)
    stops = stoppages(tracks, step)
    board = None
    sbp = os.path.join(outdir, "scoreboard.jsonl")
    if os.path.exists(sbp):
        try:
            import scoreboard as sbm
            board = sbm.analyze(sbp)
            if board["stops"]:
                stops = [[a, b] for a, b, _ in board["stops"]]
                log("Using %d stoppages read from the scoreboard clock" % len(stops))
        except Exception as e:  # keep going without the scoreboard
            log("Scoreboard readings could not be used: %s" % e)
            board = None
    log("%d pictures, %d tracks, %d suggested stoppages" % (len(rows), len(tracks), len(stops)))
    import events
    cfg = json.load(open(rink))
    faceoff_list = events.faceoffs(rows, board, cfg) if board else []
    change_list = events.changes(rows, labels, outdir, tracks, cfg)
    log("%d faceoffs, %d line change moments" % (len(faceoff_list), len(change_list)))
    import identify
    E = identify.load_emb(outdir, meta.get("emb_dim", 256))
    TLs = identify.tracklets(tracks, E, cfg, identify.load_thumbs(outdir)) if E is not None else []
    if TLs:
        log("%d tracklets with appearance fingerprints" % len(TLs))
    cap, fps = None, meta["fps"]
    if thumbs or read_nums:
        cap = cv2.VideoCapture(video)
    if read_nums and TLs and cap is not None and cap.isOpened():
        # only skaters seen big and close (numbers are readable), only a few pictures each
        try:
            import easyocr, jersey_numbers, torch
            reader = easyocr.Reader(["en"], gpu=bool(torch.cuda.is_available()), verbose=False)
            rp0 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roster.json")
            ros = {int(x["n"]) for x in json.load(open(rp0)).get("roster", [])} if os.path.exists(rp0) else set()
            byid = {tr["id"]: tr for tr in tracks}
            cand = [t for t in TLs if t["h"] >= 110]
            cand.sort(key=lambda t: -t["h"])
            for ci, t in enumerate(cand[:250]):
                pts = [q for q in byid[t["id"]]["pts"] if q[3] >= 130]
                pts = sorted(pts, key=lambda q: -q[3])[:4]
                frames = []
                for q in pts:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(q[0] * fps))
                    ok, f = cap.read()
                    if ok:
                        frames.append((f, q[6:10], q[3]))
                if frames:
                    r = jersey_numbers.read_track(frames, reader, ros, max_samples=4)
                    if r["best"]:
                        t["num"] = {"n": r["best"], "votes": r["cands"][0]["votes"], "roster": r["cands"][0]["roster"]}
                if ci % 25 == 0:
                    log("Numbers: %d of %d close-up skaters" % (ci, min(250, len(cand))))
        except Exception as e:
            log("Number reading skipped: %s" % e)

    def grab(t):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = cap.read()
        return f if ok else None

    reader, roster = None, set()
    if read_nums:
        try:
            import easyocr, jersey_numbers
            import torch
            reader = easyocr.Reader(["en"], gpu=bool(torch.cuda.is_available()), verbose=False)
        except Exception as e:
            log("Number reading is off: %s" % e)
            reader = None
    for ti, tr in enumerate(tracks):
        p = tr["pts"]
        tr["thumbs"] = []
        if cap is not None:
            if reader is not None:
                frames = []
                for q in sorted(p, key=lambda q: -q[3])[:8]:
                    f = grab(q[0])
                    if f is not None:
                        frames.append((f, q[6:10], q[3]))
                tr["num"] = jersey_numbers.read_track(frames, reader, roster, max_samples=8)
            big = max(p, key=lambda q: q[3] * q[4])
            f = grab(big[0])
            if f is not None:
                tr["thumbs"].append(thumb(f, big[6:10]))
        tr["pts"] = [[q[0], q[1], q[2], q[3]] for q in p[::2]]
    samples = {}
    for g in range(k):
        cand = [tr["thumbs"][0] for tr in tracks if tr["g"] == g and tr["thumbs"]]
        if not cand:
            cand = ["data:image/jpeg;base64," + c["thumbs"][str(g)][0] for c in change_list if c["thumbs"].get(str(g))]
        samples[g] = cand[:4]
    if TLs:
        for g in range(k):
            pics = [t["th"][0] for t in sorted(TLs, key=lambda t: -t["h"]) if t["g"] == g and t["th"]]
            samples[g] = pics[:4]
        tracks = []
    data = {"meta": meta, "colours": centres, "tracklets": TLs, "samples": {str(g): s for g, s in samples.items()},
            "tracks": tracks, "stops": stops, "board": board,
            "faceoffs": faceoff_list, "changes": change_list}
    json.dump(data, open(os.path.join(outdir, "analysis.json"), "w"))
    roster = []
    rp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roster.json")
    if os.path.exists(rp):
        roster = json.load(open(rp)).get("roster", [])
    page = os.path.join(outdir, "review.html")
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "review_template.html")).read()
    ident = open(os.path.join(here, "identity.js")).read()
    html = tpl.replace("/*IDENTITY*/", ident).replace("/*DATA*/null", json.dumps(data)).replace("/*ROSTER*/[]", json.dumps(roster))
    open(page, "w").write(html)
    log("Review page written: " + page)
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["detect", "scoreboard", "build", "analyze"])
    ap.add_argument("video")
    ap.add_argument("outdir")
    ap.add_argument("--rink", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "rinks", "ingredion_rink1.json"))
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default="yolov8s.pt")
    ap.add_argument("--numbers", action="store_true")
    a = ap.parse_args()
    if a.cmd == "scoreboard":
        import scoreboard
        scoreboard.read_series(a.video, a.rink, a.outdir, step=1.0, start=a.start, end=a.end)
    elif a.cmd == "detect":
        detect(a.video, a.outdir, a.rink, a.step, a.start, a.end, a.imgsz, limit=a.limit, model_path=a.model)
    elif a.cmd == "analyze":
        import onepass
        onepass.run(a.video, a.outdir, a.rink, step=1.0, start=a.start, end=a.end, imgsz=a.imgsz,
                    model_path=a.model, limit=a.limit)
        build(a.video, a.outdir, a.rink)
    else:
        build(a.video, a.outdir, a.rink, read_nums=a.numbers)


if __name__ == "__main__":
    main()
