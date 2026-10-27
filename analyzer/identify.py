"""Turn one pass results into tracklets with appearance fingerprints and rink positions.

A tracklet is one stretch of one skater followed on screen. Each gets:
  e    a 256 number fingerprint of how the skater looks (averaged over the stretch)
  pts  where the skater was on the rink each second, as u,v (0 to 1 along and across the rink)
The review page groups similar fingerprints, asks you to name each group once, labels the rest,
and asks again only where it is unsure.
"""
import json, os
import numpy as np

import events
import onepass


def load_emb(outdir, dim=256):
    p = os.path.join(outdir, "emb.f16")
    if not os.path.exists(p):
        return None
    return np.fromfile(p, dtype=np.float16).reshape(-1, dim).astype(np.float32)


def load_thumbs(outdir):
    d = {}
    p = os.path.join(outdir, "thumbs.jsonl")
    if os.path.exists(p):
        for line in open(p):
            try:
                r = json.loads(line)
            except Exception:
                continue
            for j, k in enumerate(r["k"]):
                if k:
                    d[r["i"] + j] = k
    return d


def tracklets(tracks, E, cfg, th=None, band=110.0):
    fx, fy = onepass.far_edge(np.array(cfg["ice"], dtype=float))
    out = []
    for tr in tracks:
        p = tr["pts"]
        ws, vs = [], []
        for q in p:
            ei = q[10] if len(q) > 10 else -1
            if E is not None and 0 <= ei < len(E):
                ws.append(max(0.05, q[4]) * max(10.0, q[3]))
                vs.append(E[ei])
        if not vs:
            continue
        m = np.average(np.stack(vs), axis=0, weights=ws)
        m /= (np.linalg.norm(m) + 1e-6)
        path = []
        for q in p:
            side, zone, u, v = events.locate(cfg, q[1], q[2])
            path.append([round(q[0], 1), u, v])

        def nearb(q):
            return q[2] - float(np.interp(q[1], fx, fy)) < band
        pics = []
        if th:
            have = sorted([q for q in p if len(q) > 10 and q[10] in th], key=lambda q: -q[3])
            for q in have[:3]:
                pics.append("data:image/jpeg;base64," + th[q[10]])
        out.append({"id": tr["id"], "th": pics, "g": tr["g"], "t0": p[0][0], "t1": p[-1][0], "n": len(p),
                    "e": [int(round(x * 127)) for x in m], "pts": path,
                    "bin": bool(nearb(p[0])), "bout": bool(nearb(p[-1])),
                    "h": int(np.median([q[3] for q in p]))})
    return out
