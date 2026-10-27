/* Who is who. Pure functions, no page code, so they can be tested alone.
   T = tracklets from identify.py: {id,g,t0,t1,e:[256 ints],pts:[[t,u,v]],bin,bout}
   seeds = {tracklet id: {n: "17", w: 1 or 0.6}}   (what the person told us) */
var Identity = (function () {
  function dec(e) { var v = new Float32Array(e.length), s = 0, i; for (i = 0; i < e.length; i++) { v[i] = e[i] / 127; s += v[i] * v[i]; } s = Math.sqrt(s) || 1; for (i = 0; i < v.length; i++) v[i] /= s; return v; }
  function dot(a, b) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
  function prep(T) { T.forEach(function (t) { if (!t.v) t.v = dec(t.e); t.dur = Math.max(1, t.t1 - t.t0 + 1); }); return T; }
  // Players of one team look alike (same jersey, same colours). Take away what they all share, so what is left is what sets one player apart.
  function centre(T, isK) {
    var K = T.filter(isK), m = new Float32Array(256), W = 0, i;
    K.forEach(function (t) { for (i = 0; i < 256; i++) m[i] += t.v[i] * t.dur; W += t.dur; });
    for (i = 0; i < 256; i++) m[i] /= (W || 1);
    T.forEach(function (t) { var c = new Float32Array(256), q = 0; for (i = 0; i < 256; i++) { c[i] = t.v[i] - m[i]; q += c[i] * c[i]; } q = Math.sqrt(q) || 1; for (i = 0; i < 256; i++) c[i] /= q; t.c = c; });
  }
  function overlap(a, b) { return a.t0 <= b.t1 && b.t0 <= a.t1; }
  function endPos(t) { var p = t.pts[t.pts.length - 1]; return [p[1], p[2]]; }
  function startPos(t) { var p = t.pts[0]; return [p[1], p[2]]; }
  function near(a, b, dt) { var d = Math.hypot(a[0] - b[0], a[1] - b[1]); return d <= 0.05 + 0.14 * dt; }

  // First guess for naming: leader grouping. Longest tracklets first; a tracklet joins the group it
  // looks most like unless that group was on screen at the same moment (two skaters at once are never one player).
  function groups(T, isK, target) {
    target = target || 20; centre(T, isK);
    var K = T.filter(isK).sort(function (a, b) { return b.dur - a.dur; });
    function run(minSim) {
      var G = [];
      K.forEach(function (t) {
        var best = -1, bs = minSim;
        G.forEach(function (g, i) {
          if (g.m.some(function (x) { return overlap(x, t); })) return;
          var s = dot(t.c, g.c); if (s > bs) { bs = s; best = i; }
        });
        if (best < 0) { G.push({m: [t], c: Float32Array.from(t.c), dur: t.dur}); return; }
        var g = G[best]; g.m.push(t); g.dur += t.dur;
        var c = new Float32Array(256), i; g.m.forEach(function (x) { for (i = 0; i < 256; i++) c[i] += x.c[i] * x.dur; });
        var q = 0; for (i = 0; i < 256; i++) q += c[i] * c[i]; q = Math.sqrt(q) || 1; for (i = 0; i < 256; i++) c[i] /= q; g.c = c;
      });
      return G;
    }
    // strictest setting that still gives about the number of players on a roster
    var lo = -0.2, hi = 0.95, best = run(lo);
    if (run(hi).filter(function (g) { return g.dur >= 8; }).length <= target) return run(hi).sort(function (a, b) { return b.dur - a.dur; });
    for (var it = 0; it < 9; it++) { var mid = (lo + hi) / 2, G = run(mid); if (G.filter(function (g) { return g.dur >= 8; }).length <= target) { best = G; lo = mid; } else hi = mid; }
    best.sort(function (a, b) { return b.dur - a.dur; });
    return best;
  }

  // Label everything. Returns {lab: {id: {n, conf}}, ask: [tracklet ids, most useful first], over: [times with too many]}
  function assign(T, seeds, isK, thr) {
    thr = thr === undefined ? 0.12 : thr; centre(T, isK);
    var K = T.filter(isK), byId = {}, players = {}, lab = {};
    K.forEach(function (t) { byId[t.id] = t; });
    Object.keys(seeds).forEach(function (id) { var t = byId[id]; if (!t) return; var s = seeds[id]; (players[s.n] = players[s.n] || []).push({t: t, w: s.w}); lab[id] = {n: s.n, conf: s.w >= 1 ? 1 : 0.9, seed: true}; });
    var names = Object.keys(players);
    if (!names.length) return {lab: {}, ask: K.map(function (t) { return t.id; }), over: []};
    var proto = {};
    names.forEach(function (n) {
      var c = new Float32Array(256), W = 0; players[n].forEach(function (s) { for (var i = 0; i < 256; i++) c[i] += s.t.c[i] * s.w * s.t.dur; W += s.w * s.t.dur; });
      var q = 0, i; for (i = 0; i < 256; i++) q += c[i] * c[i]; q = Math.sqrt(q) || 1; for (i = 0; i < 256; i++) c[i] /= q; proto[n] = c;
    });
    var wi = [], be = [], flat = [];
    names.forEach(function (n) { players[n].forEach(function (x) { flat.push({n: n, t: x.t}); }); });
    for (var i1 = 0; i1 < flat.length; i1++) for (var i2 = i1 + 1; i2 < flat.length && i2 < i1 + 60; i2++) {
      if (overlap(flat[i1].t, flat[i2].t) && flat[i1].n === flat[i2].n) continue;
      (flat[i1].n === flat[i2].n ? wi : be).push(dot(flat[i1].t.c, flat[i2].t.c)); }
    var mean = function (a, d) { return a.length ? a.reduce(function (q, x) { return q + x; }, 0) / a.length : d; };
    var within = mean(wi, 0.6), between = mean(be, 0), sepa = Math.max(0.05, within - between);
    function sim(t, n) {
      var best = -1, tot = 0, W = 0;
      players[n].forEach(function (s) { var d = dot(t.c, s.t.c); if (d > best) best = d; tot += d * s.w; W += s.w; });
      return 0.5 * best + 0.25 * (tot / W) + 0.25 * dot(t.c, proto[n]);
    }
    function busy(n, t, except) { return (players[n] || []).some(function (s) { return s.t.id !== except && overlap(s.t, t); }) || K.some(function (o) { return lab[o.id] && lab[o.id].n === n && o.id !== t.id && overlap(o, t); }); }
    function cont(n, t) {   // follows on from, or into, a tracklet already known to be this player
      var b = 0;
      K.forEach(function (o) { var l = lab[o.id]; if (!l || l.n !== n || l.conf < 0.5) return;
        if (o.t1 <= t.t0 && t.t0 - o.t1 <= 4 && near(endPos(o), startPos(t), t.t0 - o.t1)) b = Math.max(b, 0.12);
        if (t.t1 <= o.t0 && o.t0 - t.t1 <= 4 && near(endPos(t), startPos(o), o.t0 - t.t1)) b = Math.max(b, 0.12); });
      return b;
    }
    var todo = K.filter(function (t) { return !seeds[t.id]; });
    for (var pass = 0; pass < 3; pass++) {
      todo.forEach(function (t) { if (pass === 0 || (lab[t.id] && lab[t.id].conf < 0.5)) delete lab[t.id]; });
      var cand = [];
      todo.forEach(function (t) {
        if (pass > 0 && lab[t.id]) return;
        var sc = names.map(function (n) { return {n: n, s: sim(t, n) + cont(n, t)}; }).sort(function (a, b) { return b.s - a.s; });
        sc.forEach(function (x, i) { cand.push({t: t, n: x.n, s: x.s, margin: x.s - (sc[i + 1] ? sc[i + 1].s : x.s - 0.2), rank: i}); });
      });
      cand.sort(function (a, b) { return b.s - a.s; });
      var done = {};
      cand.forEach(function (c) {
        if (done[c.t.id] || lab[c.t.id]) return;
        if (busy(c.n, c.t)) return;
        if (c.s < 0.15) return;
        lab[c.t.id] = {n: c.n, conf: Math.max(0, Math.min(1, (c.margin / sepa) * 0.8)) * Math.max(0, Math.min(1, (c.s - between) / sepa)), sim: c.s}; done[c.t.id] = 1;
      });
    }
    var ask = K.filter(function (t) { var l = lab[t.id]; return !(l && l.seed) && (!l || l.conf < 0.5); })
      .sort(function (a, b) { var la = lab[a.id], lb = lab[b.id]; return b.dur * (1 - (lb ? lb.conf : 0)) - a.dur * (1 - (la ? la.conf : 0)); })
      .map(function (t) { return t.id; });
    // too many Kings skaters at once means a label is wrong somewhere
    var over = [], tmax = 0; K.forEach(function (t) { if (t.t1 > tmax) tmax = t.t1; });
    for (var s = 0; s <= tmax; s += 1) { var cnt = {}; K.forEach(function (t) { if (lab[t.id] && t.t0 <= s && s <= t.t1) cnt[lab[t.id].n] = 1; }); if (Object.keys(cnt).length > 6) over.push(s); }
    return {lab: lab, ask: ask, over: over, sepa: sepa};
  }

  // Shifts, ice time, paths and heat from the labels. stops = [[a,b],...] video seconds when the clock was stopped.
  function stats(T, lab, stops, bridge) {
    bridge = bridge || 8;
    var by = {};
    T.forEach(function (t) { var l = lab[t.id]; if (!l) return; (by[l.n] = by[l.n] || []).push(t); });
    var out = {};
    Object.keys(by).forEach(function (n) {
      var ts = by[n].sort(function (a, b) { return a.t0 - b.t0; }), sh = [];
      ts.forEach(function (t) { var l = sh[sh.length - 1]; if (l && t.t0 - l.b <= bridge) { l.b = Math.max(l.b, t.t1); l.pts = l.pts.concat(t.pts); } else sh.push({a: t.t0, b: t.t1, pts: t.pts.slice()}); });
      var toi = 0;
      sh.forEach(function (s) {
        var run = s.b - s.a;
        (stops || []).forEach(function (st) { var o = Math.min(s.b, st[1]) - Math.max(s.a, st[0]); if (o > 0) run -= o; });
        s.clock = Math.max(0, run); toi += s.clock;
        s.pts.sort(function (x, y) { return x[0] - y[0]; });
      });
      out[n] = {shifts: sh, toi: toi, video: sh.reduce(function (q, s) { return q + (s.b - s.a); }, 0)};
    });
    return out;
  }
  function heat(pts, nx, ny) {
    nx = nx || 40; ny = ny || 17; var h = new Array(nx * ny).fill(0);
    pts.forEach(function (p) { var x = Math.min(nx - 1, Math.max(0, Math.floor(p[1] * nx))), y = Math.min(ny - 1, Math.max(0, Math.floor(p[2] * ny))); h[y * nx + x]++; });
    return h;
  }
  return {prep: prep, centre: centre, groups: groups, assign: assign, stats: stats, heat: heat, dot: dot, overlap: overlap};
})();
if (typeof module !== "undefined") module.exports = Identity;
