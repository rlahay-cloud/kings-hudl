"""One pass through the game video: scoreboard, skaters and bench pictures together.

The old way read the video three separate times and jumped around inside it, which is very slow.
This reads it once, in order. It writes:
  scoreboard.jsonl   what the scoreboard showed each second
  detections.jsonl   every skater on the ice each second (skipped while the clock sits still a long time)
  bench.jsonl        tiny pictures of skaters standing near the bench boards (for line change review)
  meta.json
and it can be stopped and started again.
"""
import base64, json, os, time
import numpy as np
import cv2

import kings_analyzer as ka
import scoreboard as sbm


def _sig_diff(a, b):
    a = np.array([int(c) for c in a], dtype=np.float32)
    b = np.array([int(c) for c in b], dtype=np.float32)
    return float(np.abs(a - b).sum() / (a.sum() + b.sum() + 1e-6))


def far_edge(poly):
    """The far boards as a function of x: the top edge of the ice outline."""
    pts = poly[np.argsort(poly[:, 0])]
    xs, ys = [], []
    # for each x take the smallest y of the polygon outline at that x (top edge)
    for x in np.linspace(poly[:, 0].min(), poly[:, 0].max(), 80):
        col = []
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (x1 <= x <= x2 or x2 <= x <= x1) and x1 != x2:
                col.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
        if col:
            xs.append(x)
            ys.append(min(col))
    return np.array(xs), np.array(ys)


EMB_DIM = 256


def body_square(frame, box, size=128):
    """The skater cut out, padded to a square so a picture model sees the whole body."""
    x1, y1, x2, y2 = [int(v) for v in box]
    c = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
    if c.size == 0:
        return np.full((size, size, 3), 114, np.uint8)
    h, w = c.shape[:2]
    sc = size / float(max(h, w))
    c = cv2.resize(c, (max(2, int(w * sc)), max(2, int(h * sc))), interpolation=cv2.INTER_AREA)
    out = np.full((size, size, 3), 114, np.uint8)
    oy, ox = (size - c.shape[0]) // 2, (size - c.shape[1]) // 2
    out[oy:oy + c.shape[0], ox:ox + c.shape[1]] = c
    return out


def embed(model, crops):
    if not crops:
        return np.zeros((0, EMB_DIM), np.float16)
    e = model.embed(crops, imgsz=128, verbose=False)
    e = np.stack([x.cpu().numpy().reshape(-1) for x in e]).astype(np.float32)
    e /= (np.linalg.norm(e, axis=1, keepdims=True) + 1e-6)
    return e.astype(np.float16)


def thumb_small(frame, box, h_out=72):
    x1, y1, x2, y2 = [int(v) for v in box]
    c = frame[max(0, y1):y2, max(0, x1):x2]
    if c.size == 0:
        return ""
    s = h_out / float(c.shape[0])
    c = cv2.resize(c, (max(6, int(c.shape[1] * s)), h_out), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buf).decode()


def run(video, outdir, rink_json, step=1.0, start=0.0, end=None, imgsz=1280, conf=0.25,
        model_path="yolov8s.pt", idle_skip=60.0, limit=None, log=print):
    from ultralytics import YOLO
    import easyocr
    os.makedirs(outdir, exist_ok=True)
    cfgall = json.load(open(rink_json))
    cfg = cfgall["scoreboard"]
    cap = cv2.VideoCapture(video)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    end = min(end if end is not None else total, total)
    name, poly = ka.load_rink(rink_json, W, H)
    y0 = max(0, int(poly[:, 1].min()) - 130)
    tiles = ka.tiles_for(W, y0, H)
    sc = sbm.make_scaler(W, cfgall.get("width", W))
    fx, fy = far_edge(poly)
    bench_band = 230.0 * W / 4080.0

    # Results left by an older program or a different part of the video must never be mixed in.
    mp = os.path.join(outdir, "meta.json")
    stale = False
    if os.path.exists(mp):
        try:
            old = json.load(open(mp))
            stale = not (old.get("version") == 3 and old.get("video") == os.path.basename(video)
                         and old.get("step") == step and abs(old.get("start", 0) - start) < 1e-6
                         and old.get("end_req") == end)
        except Exception:
            stale = True
    if stale:
        log("Found results from an earlier run with different settings. Starting fresh.")
        for fn in ("scoreboard.jsonl", "detections.jsonl", "bench.jsonl", "thumbs.jsonl", "emb.f16",
                   "analysis.json", "review.html"):
            fp = os.path.join(outdir, fn)
            if os.path.exists(fp):
                os.remove(fp)
    paths = {k: os.path.join(outdir, k + ".jsonl") for k in ("scoreboard", "detections", "bench")}
    t = start
    last = None
    for line in open(paths["scoreboard"]) if os.path.exists(paths["scoreboard"]) else []:
        try:
            last = json.loads(line)["t"]
        except Exception:
            pass
    if last is not None:
        t = max(t, last + step)
        log("Carrying on from %.0f s" % t)
    json.dump({"video": os.path.basename(video), "w": W, "h": H, "fps": fps, "step": step, "rink": name,
               "duration": total, "version": 3, "emb_dim": EMB_DIM, "start": start, "end_req": end}, open(os.path.join(outdir, "meta.json"), "w"))

    gpu = sbm._has_gpu()
    model = YOLO(model_path)
    emb_model = YOLO("yolov8n-cls.pt")
    emb_path = os.path.join(outdir, "emb.f16")
    emb_rows = os.path.getsize(emb_path) // (EMB_DIM * 2) if os.path.exists(emb_path) else 0
    femb = open(emb_path, "ab")
    fth = open(os.path.join(outdir, "thumbs.jsonl"), "a")
    reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
    fsb, fdt, fbn = (open(paths[k], "a") for k in ("scoreboard", "detections", "bench"))
    stride = max(1, int(round(step * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    prev_sig, still_since, done, t0 = None, t, 0, time.time()
    while t < end:
        ok, frame = cap.read()
        if not ok:
            break
        rec = sbm.read_frame(frame, cfg, sc, reader)
        rec["t"] = round(t, 2)
        fsb.write(json.dumps(rec) + "\n")
        moved = prev_sig is None or _sig_diff(rec["clock_sig"], prev_sig) > 0.12
        if moved:
            still_since = t
        prev_sig = rec["clock_sig"]
        if t - still_since <= idle_skip:
            crops = [frame[y:y + h, x:x + w] for (x, y, w, h) in tiles]
            res = model.predict(crops, imgsz=imgsz, conf=conf, classes=[0], verbose=False,
                                device=0 if gpu else None)
            boxes, scores = [], []
            for (tx, ty, _, _), r in zip(tiles, res):
                for b, s in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
                    x1, y1, x2, y2 = b[0] + tx, b[1] + ty, b[2] + tx, b[3] + ty
                    bw, bh = x2 - x1, y2 - y1
                    if bh < 18 or bh > 300 or bw / bh > 1.8 or bw / bh < 0.18:
                        continue
                    if not ka.on_ice(poly, (x1 + x2) / 2, y2):
                        continue
                    boxes.append([x1, y1, x2, y2])
                    scores.append(float(s))
            dets = []
            for i in ka.nms(boxes, scores):
                x1, y1, x2, y2 = boxes[i]
                d = [round(x1), round(y1), round(x2), round(y2), round(scores[i], 2)] + \
                    ka.torso_rgb(frame, int(x1), int(y1), int(x2), int(y2))
                dets.append(d)
                edge = float(np.interp((x1 + x2) / 2.0, fx, fy))
                if y2 - edge < bench_band:  # standing near the far boards where the benches are
                    fbn.write(json.dumps({"t": round(t, 2), "i": len(dets) - 1, "x": round((x1 + x2) / 2),
                                          "y": round(y2), "img": thumb_small(frame, (x1, y1, x2, y2))}) + "\n")
            vecs = embed(emb_model, [body_square(frame, d[:4]) for d in dets])
            femb.write(vecs.tobytes())
            if int(round(t)) % 3 == 0:  # a small picture of some skaters, so the review page can show who is who
                fth.write(json.dumps({"i": emb_rows, "k": [thumb_small(frame, d[:4], 64) if (d[3] - d[1]) >= 36 else "" for d in dets]}) + "\n")
            fdt.write(json.dumps({"t": round(t, 2), "d": dets, "e": emb_rows}) + "\n")
            emb_rows += len(dets)
        else:
            fdt.write(json.dumps({"t": round(t, 2), "d": [], "skip": 1}) + "\n")
        for f in (fsb, fdt, fbn, femb, fth):
            f.flush()
        done += 1
        if done % 30 == 0:
            el = time.time() - t0
            log("%.0f of %.0f seconds of video done (%.1f s of work per second of video)" % (t, end, el / done))
        if limit and done >= limit:
            break
        t += step
        for _ in range(stride - 1):
            if not cap.grab():
                break
    for f in (fsb, fdt, fbn, femb, fth):
        f.close()
    log("Pass finished: %d seconds of video" % done)
    return outdir
