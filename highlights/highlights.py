"""Kings Film Room highlight video maker.

Reads the clip list that Kings Film Room already has for a game (every Kings goal, plus the clips
tagged Highlight in Coach's Corner), cuts those moments out of the full game video on this
computer, and joins them into one video. Nothing is uploaded.

Times in Kings Film Room are seconds into the main game video. If your video file starts at a
different moment than that one, use the offset (seconds to add to every time, can be negative).

Each clip gets a Kings lower third with the player's number and name. When the game has extra camera
angles in Kings Film Room and you give their video files, every goal is shown again from the camera behind
the net the Kings scored on.

Command line:
    python highlights.py 2026-10-18 "C:\\Videos\\game.mp4"
    python highlights.py 2026-10-18 game.mp4 --offset -12 --test
    python highlights.py 2026-10-18 game.mp4 --angle "Home Cam=home.mp4" --angle "Away Cam=away.mp4" --attack "Home Cam"
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

try:
    import graphic
except Exception:  # Pillow missing: clips are still cut, just without the graphic
    graphic = None

REPO = "rlahay-cloud/kings-hudl"
RAW = "https://raw.githubusercontent.com/%s/main/games/" % REPO
LEAD_GOAL, TAIL_GOAL = 10.0, 5.0
LEAD_CLIP, TAIL_CLIP = 2.0, 2.0
LEAD_POINT, TAIL_POINT = 5.0, 8.0
LEAD_SAVE, TAIL_SAVE = 4.0, 3.0
REPLAY_LEAD, REPLAY_TAIL = 8.0, 2.0  # the same window the Film Room plays around a mark
SLOW_FROM = 3.0  # a slowed replay runs at normal speed, then goes to half speed this many seconds before the mark
MAX_WIDTH = 1920
VERT_SIZE = (1080, 1920)
VERT_SCALE = 0.72  # graphics are drawn smaller in the tall picture


# ---------- the clip list from Kings Film Room ----------
def hms(text):
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", text.strip())
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kings-hudl-highlights"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def game_dates():
    """Dates that have a video review or clips on Kings Film Room, newest first."""
    names = json.loads(_get(RAW + "index.json"))
    dates = set()
    for n in names:
        m = re.match(r"^(?:review|clips)_(\d{4}-\d{2}-\d{2})", n)
        if m:
            dates.add(m.group(1))
    return sorted(dates, reverse=True)


def fetch_game_files(date, local_dir=None):
    """Returns {"review": [text, ...], "clips": [text, ...]} for the date."""
    if local_dir:
        names = sorted(os.listdir(local_dir))
        read = lambda n: open(os.path.join(local_dir, n), encoding="utf-8").read()
    else:
        names = json.loads(_get(RAW + "index.json"))
        read = lambda n: _get(RAW + n)
    out = {"review": [], "clips": []}
    for n in names:
        for kind in ("review", "clips"):
            if n.startswith("%s_%s" % (kind, date)) and n.endswith(".txt"):
                out[kind].append(read(n))
    return out


def players_text(field):
    nums = re.findall(r"[ai]?\d+", field or "", flags=re.I)
    main, assists = [], []
    for t in nums:
        n = re.sub(r"\D", "", t)
        if t[0].lower() == "i":
            continue
        if t[0].lower() == "a":
            if n not in assists:
                assists.append(n)
        elif n not in main:
            main.append(n)
    return main, assists


def in_highlight_list(field):
    """True when a clip or mark sits in a playlist whose name starts with Highlight."""
    return any(p.strip().lower().startswith("highlight") for p in (field or "").split(";"))


def short_tag(tag):
    return re.sub(r"^(For|Against): ", "", tag).strip() or "Highlight"


# ---------- roster and camera angles from Kings Film Room ----------
def fetch_roster(local_dir=None):
    """{"17": "Camden Hudson", ...} for skaters and goalies. Empty if it cannot be read."""
    try:
        if local_dir:
            text = open(os.path.join(os.path.dirname(os.path.abspath(local_dir)), "roster.json"), encoding="utf-8").read()
        else:
            text = _get("https://raw.githubusercontent.com/%s/main/roster.json" % REPO)
        d = json.loads(text)
        return {str(p["n"]): p.get("name", "") for p in (d.get("roster", []) + d.get("goalies", []))}
    except Exception:
        return {}


def parse_sync(text):
    """Period starts and extra angles from the game's sync file."""
    periods, angles, opp = {}, [], ""
    for line in (text or "").splitlines():
        a = line.strip().split("|")
        try:
            if a[0] == "P" and len(a) >= 3:
                periods[int(a[1])] = float(a[2])
            elif a[0] == "G" and len(a) >= 2:
                opp = a[1].strip()
            elif a[0] == "A" and len(a) >= 4:
                angles.append({"name": a[1].strip(), "url": a[2].strip(), "off": float(a[3])})
        except ValueError:
            continue
    return {"periods": periods, "angles": angles, "opp": opp}


def fetch_sync(date, local_dir=None):
    try:
        if local_dir:
            text = open(os.path.join(local_dir, "sync_%s.txt" % date), encoding="utf-8").read()
        else:
            text = _get(RAW + "sync_%s.txt" % date)
    except Exception:
        text = ""
    return parse_sync(text)


def period_at(sync, sec):
    p = 0
    for k, v in sorted((sync or {}).get("periods", {}).items()):
        if sec >= v - 5:
            p = k
    return p or None


def _lists(field):
    return [p.strip() for p in (field or "").split(";") if p.strip()]


def guess_pan(it, attack_side="Right"):
    """Where the action is across the main video (0 left to 1 right), from the mark's place on the ice.
    The Film Room draws the Kings attacking to the right; the Kings really attack the attack_side of the
    picture in period 1 and swap sides every period."""
    x = it.get("x")
    if x is None:
        return 0.5
    if it["kind"] == "goal":
        x = max(x, 0.85)  # follow the net the goal went into, not where the shot came from
    elif it["tag"] in ("Against: Goal", "Goal against"):
        x = min(x, 0.15)
    p = it.get("period") or 1
    right = (attack_side != "Left") == (p % 2 == 1)
    return min(0.95, max(0.05, x if right else 1.0 - x))


def collect_all(files):
    """Every mark Kings Film Room has for the game as a pickable clip:
    {id, sec, end, label, kind, tag, num, assists, period, lists, default}. default is True for goals and
    anything in a playlist whose name starts with Highlight."""
    items = []

    def add(kind, sec, end, tag, main, assists, period, lists, label=None, xpos=None):
        num = None
        if kind == "goal":
            scorer = [n for n in main if n not in assists]
            num = scorer[0] if scorer else None
        elif main:
            num = main[0]
        lab = label or (tag + (" #" + num if num else ""))
        if kind == "goal":
            lab = "Goal" + (" #" + num if num else "") + (" (A " + ", ".join("#" + n for n in assists) + ")" if assists else "")
        items.append({"id": "%d|%s" % (sec, tag), "sec": float(sec), "end": end, "label": lab, "kind": kind, "tag": tag,
                      "num": num, "assists": list(assists), "period": period, "lists": lists, "x": xpos,
                      "default": kind == "goal" or any(p.lower().startswith("highlight") for p in lists)})

    for text in files.get("review", []):
        for line in text.splitlines():
            a = line.split("|")
            if len(a) < 4:
                continue
            sec = hms(a[0])
            if sec is None or not a[1].strip():
                continue
            tag = a[1].strip()
            main, assists = players_text(a[2])
            m = re.match(r"^[^,]*,[^,]*,(\d+)", a[3])
            period = int(m.group(1)) if m else None
            mx = re.match(r"^(0?\.\d+|[01](?:\.\d+)?),", a[3])
            xp = float(mx.group(1)) if mx else None
            lists = _lists(a[4]) if len(a) > 4 else []
            if tag == "Against: Shot on goal":
                add("save", sec, None, "Save", main, [], period, lists, xpos=xp)
            elif tag == "For: Goal":
                add("goal", sec, None, "Goal", main, assists, period, lists, xpos=xp)
            else:
                add("clip", sec, None, tag.replace("For: ", ""), main, [], period, lists, xpos=xp)
    seen = {(round(i["sec"]), i["tag"]) for i in items}
    goal_secs = [i["sec"] for i in items if i["kind"] == "goal"]
    for text in files.get("clips", []):
        for line in text.splitlines():
            a = line.split("|")
            if len(a) < 4:
                continue
            sec = hms(a[0])
            tag = a[1].strip()
            if sec is None or not tag:
                continue
            end = None
            lab = a[3].strip()
            if len(a) > 4 and re.match(r"^\d{1,7}$", a[4].strip()):
                end = float(a[4].strip())
            if end is not None and end <= sec:
                end = None
            main, assists = players_text(a[2])
            lists = _lists(a[5]) if len(a) > 5 else []
            if tag == "Goal":
                if any(abs(g - sec) <= 4 for g in goal_secs):
                    continue
                add("goal", sec, None, "Goal", main, assists, None, lists)
            else:
                name = lab or (tag if tag != "Highlight" else "Highlight")
                if (round(sec), tag.replace("For: ", "")) in seen:
                    continue
                add("clip", sec, end, name, main, [], None, lists, label=name)
    items.sort(key=lambda i: i["sec"])
    mark_situations(items, files)
    return items


ASSUME_PEN_SEC = 150  # same guess Kings Film Room uses for a penalty with no end time


def _penalties(files):
    """(who, start, until or None) for each penalty in the review: who is 'us' or 'them'."""
    pens = []
    for text in files.get("review", []):
        for line in text.splitlines():
            a = line.split("|")
            if len(a) < 4:
                continue
            tag = a[1].strip()
            if tag not in ("Penalty", "Away Penalty"):
                continue
            sec = hms(a[0])
            if sec is None:
                continue
            ms = re.search(r",s(\d+)", a[3])
            me = re.search(r",e(\d+)", a[3])
            pens.append(("us" if tag == "Penalty" else "them", float(ms.group(1)) if ms else float(sec),
                         float(me.group(1)) if me else None))
    return pens


def mark_situations(items, files):
    """Set it['sit'] to PP (power play) or SH (short handed) for goals scored while a penalty was running, and say so in
    the label. The same rules as the Film Room: a penalty with no end time lasts 2.5 minutes of video, or until the other
    team scores, unless the other team also has a penalty running."""
    pens = _penalties(files)
    if not pens:
        return
    goals_for = [i["sec"] for i in items if i["kind"] == "goal"]
    goals_against = [i["sec"] for i in items if is_goal_against(i)]

    def end_of(p):
        who, start, until = p
        if until is not None:
            return until
        end = start + ASSUME_PEN_SEC
        goals = goals_against if who == "us" else goals_for
        for g in goals:
            if g < start or g >= end:
                continue
            other = any(q[0] != who and q[1] <= g <= (q[2] if q[2] is not None else q[1] + ASSUME_PEN_SEC) for q in pens)
            if not other:
                end = g
        return end

    spans = [(p[0], p[1], end_of(p)) for p in pens]
    for it in items:
        scored_by = "us" if it["kind"] == "goal" else "them" if is_goal_against(it) else None
        if not scored_by:
            continue
        us = sum(1 for w, a, b in spans if w == "us" and a <= it["sec"] <= b)
        th = sum(1 for w, a, b in spans if w == "them" and a <= it["sec"] <= b)
        if scored_by == "us":
            sit = "PP" if th > us else "SH" if us > th else None
        else:
            sit = "PP" if us > th else "SH" if th > us else None
        if sit:
            it["sit"] = sit
            if it["kind"] == "goal":
                it["label"] += " PP" if sit == "PP" else " SH"


def collect(files):
    """The usual clips: goals, anything in a Highlight playlist, and saves."""
    return [i for i in collect_all(files) if i["default"] or i["kind"] == "save"]


def catalog(date, local_dir=None):
    """All marks of a game for the picking list, with periods filled in."""
    items = collect_all(fetch_game_files(date, local_dir))
    sync = fetch_sync(date, local_dir)
    for it in items:
        if not it.get("period"):
            it["period"] = period_at(sync, it["sec"])
    return items


def is_goal_for(it):
    return it["kind"] == "goal"


def is_goal_against(it):
    return it["tag"] in ("Against: Goal", "Goal against")


def score_map(all_items):
    """{second of the goal: (kings, them)} after each goal, from every goal marked for the game."""
    ev, last_against = [], None
    for i in sorted(all_items, key=lambda x: x["sec"]):
        if is_goal_for(i):
            ev.append((i["sec"], "us"))
        elif is_goal_against(i):
            if i["tag"] == "Goal against" and any(abs(i["sec"] - t) <= 4 for t, w in ev if w == "them"):
                continue  # the same goal from a clips file
            ev.append((i["sec"], "them"))
    us = them = 0
    out = {}
    for sec, who in sorted(ev):
        if who == "us":
            us += 1
        else:
            them += 1
        out[round(sec)] = (us, them, who)
    return out


def caption_for(it, roster):
    """What the lower third says for one clip: (tag, number, name, second line)."""
    nm = lambda n: roster.get(str(n), "")
    sub = None
    if it["kind"] == "goal":
        if it["assists"]:
            sub = "Assists: " + ", ".join(("#%s %s" % (n, nm(n))).strip() for n in it["assists"])
        else:
            sub = "Unassisted"
    num = it.get("num")
    if it["kind"] == "goal" or it["kind"] == "save" or num:
        tag = it.get("tag") or "Highlight"
        if it["kind"] == "goal" and it.get("sit"):
            tag = "Power Play Goal" if it["sit"] == "PP" else "Short Handed Goal"
        return tag, num, (nm(num) if num else None), sub
    return "Highlight", None, it.get("tag") or "Highlight", sub


def bounds(it):
    if it["kind"] == "goal":
        return LEAD_GOAL, TAIL_GOAL
    if it["kind"] == "save":
        return LEAD_SAVE, TAIL_SAVE
    return None


def segments(items, offset=0.0, video_len=None):
    """Start and end of each cut, in the video file's own time. Overlaps are joined and keep their clips."""
    segs = []
    for it in items:
        if it["kind"] == "goal":
            s, e = it["sec"] - LEAD_GOAL, it["sec"] + TAIL_GOAL
        elif it["kind"] == "save":
            s, e = it["sec"] - LEAD_SAVE, it["sec"] + TAIL_SAVE
        elif it["end"]:
            s, e = it["sec"] - LEAD_CLIP, it["end"] + TAIL_CLIP
        else:
            s, e = it["sec"] - LEAD_POINT, it["sec"] + TAIL_POINT
        s, e = s + offset, e + offset
        if e <= 0 or (video_len and s >= video_len):
            continue
        segs.append({"start": max(0.0, s), "end": min(e, video_len) if video_len else e, "label": it["label"],
                     "items": [it]})
    segs.sort(key=lambda x: x["start"])
    merged = []
    for s in segs:
        if merged and s["start"] <= merged[-1]["end"] + 1.0:
            m = merged[-1]
            m["end"] = max(m["end"], s["end"])
            m["items"] += s["items"]
            if s["label"] not in m["label"]:
                m["label"] += " / " + s["label"]
        else:
            merged.append(dict(s))
    return merged


# ---------- which camera shows a goal ----------
def pick_cam(angles, attack, period, kings_scored=True):
    """The camera behind the net the Kings scored on. attack is the name of the camera at the Kings' attacking end
    in period 1; teams swap ends every period, so even periods use the other camera."""
    if not angles:
        return None
    atk = next((a for a in angles if a["name"] == attack), angles[0])
    others = [a for a in angles if a is not atk]
    pref = [a for a in others if re.search(r"home|away", a["name"], re.I)] or others
    other = pref[0] if pref else None
    flip = bool(period and period % 2 == 0) != (not kings_scored)
    return other if flip and other else atk


def replay_segment(it, angle):
    """Start and end of a replay in the angle video's own time. This is the Film Room's own window around the mark
    (8 seconds before, 2 after) moved by the angle's sync offset (angle time = main time + offset).
    The computer's "seconds to add" is for the main video file only and is not used here."""
    if it["kind"] != "goal" and it.get("end") and it["end"] > it["sec"]:
        s, e = it["sec"] - LEAD_CLIP, it["end"] + TAIL_CLIP
    else:
        s, e = it["sec"] - REPLAY_LEAD, it["sec"] + REPLAY_TAIL
    return {"start": max(0.0, s + angle["off"]), "end": e + angle["off"]}


def find_ffmpeg(log=print):
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    log("Getting the video cutting program (one time, about a minute)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"],
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("Could not get the video cutting program: %s" % e)


def video_info(ffmpeg, video):
    """(seconds, width, height, has_audio) of a video file."""
    p = subprocess.run([ffmpeg, "-i", video], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True,
                       encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", p.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    v = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", p.stderr)
    w, h = (int(v.group(1)), int(v.group(2))) if v else (1920, 1080)
    return dur, w, h, "Audio:" in p.stderr


def fit_size(w, h):
    """Output size for a video: at most MAX_WIDTH wide, even numbers."""
    ow = min(w, MAX_WIDTH)
    ow -= ow % 2
    oh = int(round(h * ow / float(w)))
    return ow, oh - oh % 2


def video_length(ffmpeg, video):
    return video_info(ffmpeg, video)[0]


_NVENC = {}


def use_gpu(ffmpeg, log=print):
    """True when the Dell's graphics card can do the video encoding (NVIDIA NVENC). Tested once with a tiny clip."""
    if ffmpeg in _NVENC:
        return _NVENC[ffmpeg]
    ok = False
    try:
        r = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=256x144:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"],
                           stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
    except Exception:
        ok = False
    _NVENC[ffmpeg] = ok
    log("Using the graphics card for cutting." if ok else "Using the processor for cutting.")
    return ok


def _run(cmd):
    """Runs ffmpeg. If the graphics card encoder fails, runs again with the processor."""
    r = _run1(cmd)
    if r.returncode != 0 and "h264_nvenc" in cmd:
        _NVENC[cmd[0]] = False
        r = _run1(_cpu_cmd(cmd))
    return r


def _cpu_cmd(cmd):
    out = list(cmd)
    i = out.index("h264_nvenc")
    out[i] = "libx264"
    j = out.index("-cq")
    out[j:j + 2] = ["-crf", "22"]
    k = out.index("-preset")
    out[k + 1] = "veryfast"
    return out


def _run1(cmd):
    return subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _fades(d, fade):
    """ffmpeg fade pieces for a corner graphic that lasts d seconds."""
    return ("fade=t=in:st=0:d=0.3:alpha=1," if fade[0] else "") + ("fade=t=out:st=%.2f:d=0.4:alpha=1," % max(0.0, d - 0.5) if fade[1] else "")


def cut_one(ffmpeg, video, seg, out, cap, info, tmp, log, chip=None, item_sec=None, target=None, slow=False, zoom=1.0, bug=None, fade=(True, True), pan=None):
    """Cuts one clip. cap is the lower third text (tag, number, name, sub) or None. chip is
    (text, is_replay) for the camera tag in the top left, or None. info is video_info(video).
    bug is {"args": (us_name, us, them_name, them, scored), "t0": seconds into this clip} for the score in the top right.
    fade says whether the corner graphics fade in at the start and out at the end (a replay in two parts fades once)."""
    dur_s, w, h, has_audio = info
    bed = seg.get("bed") if slow else None  # slowed sound is garbled, so slow motion plays the crowd from the main video
    if slow:
        has_audio = False
    out_w, out_h = target or fit_size(w, h)
    fit = "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24" % (out_w, out_h, out_w, out_h)
    scale = out_w / 1920.0
    if pan is not None:  # vertical for phones: a tall slice of the picture, centred on pan (0 left to 1 right)
        fit = ("crop=w='min(iw,ih*%d/%d)':h=ih:x='max(0,min(iw-ow,%.4f*iw-ow/2))':y=0,scale=%d:%d,setsar=1,fps=24"
               % (out_w, out_h, min(1.0, max(0.0, pan)), out_w, out_h))
        scale = out_w / 1080.0 * VERT_SCALE
    length = seg["end"] - seg["start"]
    f = 2.0 if slow else 1.0  # half speed makes the clip twice as long on screen
    out_len = length * f
    pre = ("crop=iw/%.3f:ih/%.3f," % (zoom, zoom) if zoom and zoom > 1.0 else "") + ("setpts=2*PTS," if slow else "")
    fit = pre + fit
    base = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", "%.2f" % seg["start"], "-i", video]
    vcodec = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"] if use_gpu(ffmpeg) else \
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
    enc = vcodec + ["-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-t", "%.2f" % out_len, out]
    audio_in, amap, afx = [], ["-map", "0:a:0"], []
    if not has_audio:
        if bed:
            audio_in = ["-ss", "%.2f" % bed[1], "-t", "%.2f" % out_len, "-i", bed[0]]
            afx = ["-af", "volume=0.6,afade=t=in:d=0.4,afade=t=out:st=%.2f:d=0.4" % max(0.0, out_len - 0.4)]
        else:
            audio_in = ["-f", "lavfi", "-t", "%.2f" % out_len, "-i", "anullsrc=r=44100:cl=stereo"]
        amap = None
    if (cap or chip or bug) and graphic is not None:
        try:
            inputs, chain, last, n = [], [], "[v0]", 1
            chain.append("[0:v]%s[v0]" % fit)
            if cap:
                lt = os.path.join(tmp, "lt_%d.png" % (abs(hash(out)) % 10 ** 8))
                lw, lh = graphic.lower_third(lt, scale, *cap)
                t0 = max(0.3, ((item_sec - seg["start"]) * f - 3.0) if item_sec is not None else 0.5)
                t0 = min(t0, max(0.3, out_len - 2.0))
                d = max(1.0, out_len - t0)
                x0, y0 = int(60 * scale), out_h - lh - int(60 * scale)
                inputs += ["-loop", "1", "-framerate", "24", "-t", "%.2f" % d, "-i", lt]
                chain.append("[%d:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=%.2f:d=0.4:alpha=1,setpts=PTS+%.2f/TB[g%d]"
                             % (n, d - 0.5, t0, n))
                chain.append("%s[g%d]overlay=x='if(lt(t-%.2f,0.35),-overlay_w+(%d+overlay_w)*(t-%.2f)/0.35,%d)':y=%d:eof_action=pass[v%d]"
                             % (last, n, t0, x0, t0, x0, y0, n))
                last = "[v%d]" % n
                n += 1
            if chip:
                cp = os.path.join(tmp, "chip_%d.png" % (abs(hash(out)) % 10 ** 8))
                cw, ch = graphic.angle_chip(cp, scale, chip[0], chip[1])
                d = max(1.0, out_len - 0.3)
                inputs += ["-loop", "1", "-framerate", "24", "-t", "%.2f" % d, "-i", cp]
                chain.append("[%d:v]format=rgba,%ssetpts=PTS+0.3/TB[g%d]" % (n, _fades(d, fade), n))
                chain.append("%s[g%d]overlay=x=%d:y=%d:eof_action=pass[v%d]" % (last, n, int(60 * scale), int(50 * scale), n))
                last = "[v%d]" % n
                n += 1
            if bug:
                bp = os.path.join(tmp, "bug_%d.png" % (abs(hash(out)) % 10 ** 8))
                bw, bh = graphic.score_bug(bp, scale, *bug["args"])
                t0 = min(max(0.3 if fade[0] else 0.0, bug["t0"]), max(0.3, out_len - 1.5))
                d = max(1.0, out_len - t0)
                inputs += ["-loop", "1", "-framerate", "24", "-t", "%.2f" % d, "-i", bp]
                chain.append("[%d:v]format=rgba,%ssetpts=PTS+%.2f/TB[g%d]" % (n, _fades(d, fade), t0, n))
                chain.append("%s[g%d]overlay=x=%d:y=%d:eof_action=pass[v%d]" % (last, n, out_w - bw - int(60 * scale), int(50 * scale), n))
                last = "[v%d]" % n
            # input numbering: 0 video, then each png (8 arguments per png), then the silent audio if used
            amap_cmd = amap if amap else ["-map", "%d:a" % (1 + len(inputs) // 8)]
            cmd = base + inputs + audio_in + ["-filter_complex", ";".join(chain), "-map", last] + amap_cmd + afx + enc
            r = _run(cmd)
            if r.returncode == 0:
                return
            log("Could not add the graphic, cutting without it. " + r.stderr.strip()[-200:])
        except Exception as e:
            log("Could not draw the graphic, cutting without it. %s" % e)
    cmd = base + audio_in + ["-vf", fit, "-map", "0:v"] + \
        (amap if amap else ["-map", "1:a"]) + afx + enc
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError("The cutting program stopped: " + r.stderr.strip()[-300:])


def make_video(video, date, out, offset=0.0, test=False, local_dir=None, log=print, progress=None, saves=True,
               angles=None, attack=None, slow=False, zoom=1.0, picks=None, show_score=False, vertical=False, attack_side="Right"):
    """angles: [{"name": "Home Cam", "file": "C:\\home.mp4"}]. Each goal is then shown again from the camera behind
    the net the Kings scored on (one replay, not every angle). picks is the list of clips to use (from catalog());
    a clip with replay set to True also gets a replay, goals do by default.
    slow plays the replays at half speed and zoom (like 1.5) crops in on the middle of the replay picture."""
    if picks is not None:
        items = sorted(picks, key=lambda i: i["sec"])
    else:
        items = [i for i in collect(fetch_game_files(date, local_dir)) if saves or i["kind"] != "save"]
    if not items:
        raise RuntimeError("Nothing is picked for %s yet." % date)
    ffmpeg = find_ffmpeg(log)
    info = video_info(ffmpeg, video)
    roster = fetch_roster(local_dir)
    sync = fetch_sync(date, local_dir)
    for it in items:
        if not it.get("period"):
            it["period"] = period_at(sync, it["sec"])
    scores = {}
    if show_score:
        try:
            scores = score_map(collect_all(fetch_game_files(date, local_dir)))
        except Exception:
            scores = {}
    opp_name = sync.get("opp") or "Opponent"

    def bug_for(it, t0):
        sc = scores.get(round(it["sec"]))
        if not (show_score and sc and (is_goal_for(it) or is_goal_against(it))):
            return None
        return {"args": ("Kings", sc[0], opp_name, sc[1], sc[2]), "t0": t0}

    def seg_pan(seg):
        g = next((i for i in seg["items"] if i["kind"] == "goal" or is_goal_against(i)), seg["items"][0])
        return g["pan"] if g.get("pan") is not None else guess_pan(g, attack_side)

    def self_bug(seg):
        g = next((i for i in seg["items"] if is_goal_for(i) or is_goal_against(i)), None)
        return bug_for(g, (g["sec"] + offset - seg["start"]) * (1.0) + 0.4) if g else None

    cams = []
    for a in (angles or []):
        base = next((x for x in sync["angles"] if x["name"] == a["name"]), None)
        if not a.get("file") or not base:
            continue
        if not base["off"]:
            log("Skipping %s: it is not matched to the main video yet (Game Desk, Game setup)." % a["name"])
            continue
        cams.append({"name": a["name"], "off": base["off"], "file": a["file"], "info": video_info(ffmpeg, a["file"])})
    segs = segments(items, offset, info[0])
    if not segs:
        raise RuntimeError("None of the clips fall inside this video. Check the offset.")
    if test:
        segs = segs[:1]
    target = fit_size(info[1], info[2])
    plan = []
    for s in segs:
        plan.append(("main", s, video, info, None, s["items"][0]["sec"] + offset, False, None, (True, True)))
        done = set()
        for it in s["items"]:
            want = it.get("replay", it["kind"] == "goal")
            pick = [pick_cam(cams, attack, it.get("period"), not it["tag"].startswith("Against: Goal"))] if (cams and want) else []
            for c in pick:
                if c and (c["name"], it["sec"]) not in done:
                    done.add((c["name"], it["sec"]))
                    rs = replay_segment(it, c)
                    if c["info"][0]:
                        rs["end"] = min(rs["end"], c["info"][0])
                    if rs["end"] - rs["start"] > 2:
                        lab = "Replay " + c["name"] + " " + it["label"]
                        mark = it["sec"] + c["off"]
                        if slow and rs["start"] + 1.0 < mark - SLOW_FROM < rs["end"] - 1.0:
                            cut = mark - SLOW_FROM
                            plan.append(("replay", {"start": rs["start"], "end": cut, "items": [it], "label": lab}, c["file"], c["info"], c["name"], mark, False, bug_for(it, 0.3), (True, False)))
                            bed = (video, it["sec"] + offset - SLOW_FROM) if info[3] else None
                            plan.append(("replay", {"start": cut, "end": rs["end"], "items": [it], "label": lab + " (half speed)", "bed": bed}, c["file"], c["info"], c["name"], mark, True, bug_for(it, 0.0), (False, True)))
                        else:
                            bed = (video, it["sec"] + offset - SLOW_FROM) if (slow and info[3]) else None
                            plan.append(("replay", dict(rs, items=[it], label=lab, bed=bed), c["file"], c["info"], c["name"], mark, slow, bug_for(it, 0.3), (True, True)))
    total = sum((p[1]["end"] - p[1]["start"]) * (2 if p[6] else 1) for p in plan)
    log("%d clips, %d minutes %d seconds in all." % (len(plan), total // 60, total % 60))
    tmp = tempfile.mkdtemp(prefix="kings_hl_")
    variants = [None] + (["vertical"] if vertical else [])
    n_total, n_done = len(plan) * len(variants), 0
    outs = []
    try:
        for variant in variants:
            names = []
            vt = VERT_SIZE if variant else target
            for i, (kind, s, vid, vinfo, camname, moment, is_slow, rbug, fade) in enumerate(plan):
                log("Cutting %sclip %d of %d: %s" % ("vertical " if variant else "", i + 1, len(plan), s["label"]))
                fn = os.path.join(tmp, "%s%03d.mp4" % ("v" if variant else "c", i))
                first = s["items"][0]
                chip = None
                if cams:
                    chip = ((camname + (" 0.5x" if is_slow else "") + (" zoom" if zoom > 1.0 else ""), True) if kind == "replay" else ("Main Cam", False))
                pan = None
                if variant:  # replay cameras sit behind the net, so they stay centred
                    pan = 0.5 if kind == "replay" else seg_pan(s)
                cut_one(ffmpeg, vid, s, fn, caption_for(first, roster) if kind == "main" else None, vinfo, tmp, log, chip, moment, vt,
                        is_slow, zoom if kind == "replay" else 1.0,
                        rbug if kind == "replay" else self_bug(s), fade, pan)
                names.append(fn)
                n_done += 1
                if progress:
                    progress(n_done, n_total)
            lst = os.path.join(tmp, "list%s.txt" % ("v" if variant else ""))
            with open(lst, "w", encoding="utf-8") as f:
                for n in names:
                    f.write("file '%s'\n" % n.replace("\\", "/").replace("'", "'\\''"))
            dest = out if not variant else os.path.splitext(out)[0] + "_vertical.mp4"
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            log("Joining the %sclips." % ("vertical " if variant else ""))
            r = _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                      "-i", lst, "-c", "copy", "-movflags", "+faststart", dest])
            if r.returncode != 0:
                raise RuntimeError("Could not join the clips: " + r.stderr.strip()[-300:])
            outs.append(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for o in outs:
        log("Done: " + o)
    return out


def clip_name(date, sec):
    """File name for one clip, from the game date and the mark's second in the game video."""
    return "%s_%d.mp4" % (date, int(round(sec)))


def one_segment(it, offset=0.0, video_len=None):
    """Start and end of one clip in the video file's time, or None if it falls outside the video."""
    s = segments([it], offset, video_len)
    return s[0] if s else None


def make_each(video, date, outdir, offset=0.0, test=False, local_dir=None, log=print, progress=None, saves=True):
    """Cuts every clip of the game into its own file in outdir, plus clips.json listing them.
    Clips already cut are skipped, so running it again only does new ones."""
    files = fetch_game_files(date, local_dir)
    items = [i for i in collect(files) if saves or i["kind"] != "save"]
    if not items:
        raise RuntimeError("Kings Film Room has no goals or highlight clips for %s yet." % date)
    ffmpeg = find_ffmpeg(log)
    info = video_info(ffmpeg, video)
    roster = fetch_roster(local_dir)
    todo = []
    for it in items:
        seg = one_segment(it, offset, info[0])
        if seg:
            todo.append((it, seg))
    if not todo:
        raise RuntimeError("None of the clips fall inside this video. Check the offset.")
    if test:
        todo = todo[:1]
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="kings_hl_")
    manifest = []
    try:
        for i, (it, seg) in enumerate(todo):
            name = clip_name(date, it["sec"])
            out = os.path.join(outdir, name)
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                log("Already cut: %s" % it["label"])
            else:
                log("Cutting clip %d of %d: %s" % (i + 1, len(todo), it["label"]))
                cut_one(ffmpeg, video, seg, out, caption_for(it, roster), info, tmp, log, None, it["sec"] + offset)
            manifest.append({"file": name, "sec": int(round(it["sec"])), "label": it["label"],
                             "bytes": os.path.getsize(out)})
            if progress:
                progress(i + 1, len(todo))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(outdir, "clips.json"), "w", encoding="utf-8") as f:
        json.dump({"date": date, "clips": manifest}, f, indent=1)
    log("Done. %d clips are in %s" % (len(manifest), outdir))
    return outdir


def main():
    ap = argparse.ArgumentParser(description="Make a Kings highlight video from Kings Film Room clips.")
    ap.add_argument("date", help="Game date, like 2026-10-18")
    ap.add_argument("video", help="The full game video file")
    ap.add_argument("--offset", type=float, default=0.0, help="Seconds to add to every Kings Film Room time")
    ap.add_argument("--test", action="store_true", help="Only make the first clip, to check the timing")
    ap.add_argument("--no-saves", action="store_true", help="Leave out the saves (shots against)")
    ap.add_argument("--each", action="store_true", help="Cut every clip into its own file (for the Download buttons)")
    ap.add_argument("--angle", action="append", default=[], help='Extra camera video, like "Home Cam=C:\\home.mp4"')
    ap.add_argument("--attack", default=None, help="Name of the camera at the end the Kings attack in period 1")
    ap.add_argument("--vertical", action="store_true", help="Also make a tall version for phones")
    ap.add_argument("--attack-side", default="Right", choices=["Right", "Left"], help="Side of the picture the Kings attack in period 1")
    ap.add_argument("--score", action="store_true", help="Show the score on goals and replays")
    ap.add_argument("--slow", action="store_true", help="Play the replays at half speed")
    ap.add_argument("--zoom", type=float, default=1.0, help="Zoom the replays in, like 1.5")
    ap.add_argument("--out", default=None)
    ap.add_argument("--local-dir", default=None, help="Read the game files from a folder instead of GitHub")
    a = ap.parse_args()
    if a.each:
        d = a.out or os.path.join(os.path.expanduser("~"), "Documents", "KingsHighlights", "clips_" + a.date)
        make_each(a.video, a.date, d, a.offset, a.test, a.local_dir, saves=not a.no_saves)
        return
    out = a.out or os.path.join(os.path.expanduser("~"), "Documents", "KingsHighlights",
                                "Kings_highlights_%s%s.mp4" % (a.date, "_test" if a.test else ""))
    angles = [{"name": x.split("=", 1)[0], "file": x.split("=", 1)[1]} for x in a.angle if "=" in x]
    make_video(a.video, a.date, out, a.offset, a.test, a.local_dir, saves=not a.no_saves, angles=angles,
               attack=a.attack, slow=a.slow, zoom=a.zoom, show_score=a.score,
               vertical=a.vertical, attack_side=a.attack_side)


if __name__ == "__main__":
    main()
